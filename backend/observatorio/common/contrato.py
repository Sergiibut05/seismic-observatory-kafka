"""Contratos Kafka v1 y v2 (specs/001-esqueleto/contracts/mensaje-kafka-v1.md y
specs/013-multifuente/contracts/mensajes-kafka.md).

- v1: un evento de una fuente, sin alterar. Topics por fuente, `eventos.replay`, humo y sintéticos.
- v2: un evento fusionado (lo escribe la fusión en `eventos.live`), con la lista de fuentes que lo
  componen y el original de cada una.

Única fuente de verdad en ejecución: productores, fusión, consumidor y replay lo importan.
La validación es manual y devuelve un motivo de lista cerrada, sin pydantic ni jsonschema (R-10).
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from observatorio.common.tiempo import iso_utc, ms_a_datetime

SCHEMA_VERSION = 1
SCHEMA_VERSION_FUSION = 2
MODOS = ("live", "replay")
PREFIJO_SINTETICO = "synthetic-"

_CAMPOS_RAIZ = ("schema_version", "source", "ingested_at", "mode", "event")
_CAMPOS_RAIZ_V2 = _CAMPOS_RAIZ + ("fuentes",)
_CAMPOS_FUENTE = ("fuente", "id", "updated", "principal", "original")
_PATRON_SOURCE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
_UPDATED_MAXIMO_MS = 4_102_444_800_000  # 2100-01-01 UTC


@dataclass(frozen=True)
class MensajeValido:
    event_id: str
    updated_ms: int
    updated: datetime
    source: str
    mode: str
    ingested_at: datetime
    sintetico: bool
    mensaje: dict
    # v1: `(source,)`. v2: las fuentes del evento fusionado, en orden alfabético.
    fuentes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rechazo:
    motivo: str
    detalle: str = ""
    event_id: str | None = None
    updated: int | None = None


def es_sintetico(valor: str) -> bool:
    return valor.startswith(PREFIJO_SINTETICO)


def _rechazar_constante(nombre: str):
    # `NaN` e `Infinity` no son JSON estándar y `jsonb` no los admite.
    raise ValueError(f"constante no válida: {nombre}")


def _es_entero(valor) -> bool:
    # `bool` es subclase de `int` en Python y no vale como número.
    return isinstance(valor, int) and not isinstance(valor, bool)


def _identificadores(mensaje: dict) -> tuple[str | None, int | None]:
    """`event_id` y `updated` si el mensaje los trae bien formados (para el log del rechazo)."""
    evento = mensaje.get("event")
    if not isinstance(evento, dict):
        return None, None
    event_id = evento.get("id")
    propiedades = evento.get("properties")
    updated = propiedades.get("updated") if isinstance(propiedades, dict) else None
    return (
        event_id if isinstance(event_id, str) and event_id else None,
        updated if _es_entero(updated) else None,
    )


def _parsear_ingested_at(texto: str) -> datetime | None:
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if instante.tzinfo is None or instante.utcoffset().total_seconds() != 0:
        return None
    return instante.astimezone(timezone.utc)


def validar_mensaje(clave: bytes | None, valor: bytes | None, modo_del_topic: str) -> MensajeValido | Rechazo:
    """Valida un registro Kafka. El primer fallo, en el orden del contrato, decide el motivo."""
    if valor is None:
        return Rechazo("valor_ausente", "el registro no tiene valor")
    try:
        mensaje = json.loads(valor.decode("utf-8"), parse_constant=_rechazar_constante)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        return Rechazo("json_ilegible", type(exc).__name__)
    if not isinstance(mensaje, dict):
        return Rechazo("no_es_objeto", f"raíz de tipo {type(mensaje).__name__}")

    # El campo `fuentes` solo existe en v2: la versión decide qué campos se esperan.
    campos = _CAMPOS_RAIZ_V2 if mensaje.get("schema_version") == SCHEMA_VERSION_FUSION else _CAMPOS_RAIZ
    faltan = [c for c in campos if c not in mensaje]
    sobran = sorted(c for c in mensaje if c not in campos)
    if faltan or sobran:
        detalle = ", ".join([f"falta {c}" for c in faltan] + [f"campo desconocido {c}" for c in sobran])
        return Rechazo("campo_ausente", detalle, *_identificadores(mensaje))

    def rechazo(motivo: str, detalle: str) -> Rechazo:
        return Rechazo(motivo, detalle, *_identificadores(mensaje))

    version = mensaje["schema_version"]
    if not _es_entero(version) or version not in (SCHEMA_VERSION, SCHEMA_VERSION_FUSION):
        return rechazo("schema_version_no_soportada", "schema_version")

    source = mensaje["source"]
    if not isinstance(source, str):
        return rechazo("tipo_invalido", "source")
    if not _PATRON_SOURCE.match(source):
        return rechazo("source_invalido", "source")

    modo = mensaje["mode"]
    if not isinstance(modo, str):
        return rechazo("tipo_invalido", "mode")
    if modo not in MODOS or (version == SCHEMA_VERSION_FUSION and modo != "live"):
        return rechazo("mode_invalido", "mode")
    if modo != modo_del_topic:
        return rechazo("mode_no_corresponde_al_topic", f"mode={modo} topic={modo_del_topic}")

    texto_ingesta = mensaje["ingested_at"]
    if not isinstance(texto_ingesta, str):
        return rechazo("tipo_invalido", "ingested_at")
    ingested_at = _parsear_ingested_at(texto_ingesta)
    if ingested_at is None:
        return rechazo("ingested_at_invalido", "ingested_at")

    evento = mensaje["event"]
    if not isinstance(evento, dict):
        return rechazo("tipo_invalido", "event")
    event_id = evento.get("id")
    if not isinstance(event_id, str) or not event_id:
        return rechazo("evento_sin_id", "event.id")

    if clave is None:
        return rechazo("clave_ausente", "clave")
    try:
        clave_texto = clave.decode("utf-8")
    except UnicodeDecodeError:
        return rechazo("clave_distinta_de_id", "la clave no es UTF-8")
    if clave_texto != event_id:
        return rechazo("clave_distinta_de_id", "clave != event.id")

    propiedades = evento.get("properties")
    updated_ms = propiedades.get("updated") if isinstance(propiedades, dict) else None
    if not _es_entero(updated_ms) or not 0 <= updated_ms <= _UPDATED_MAXIMO_MS:
        return rechazo("updated_invalido", "event.properties.updated")

    sintetico = es_sintetico(source)
    if sintetico != es_sintetico(event_id):
        return rechazo("sintetico_inconsistente", "source y event.id no coinciden en el prefijo synthetic-")

    fuentes: tuple[str, ...] = (source,)
    if version == SCHEMA_VERSION_FUSION:
        nombres, fallo = _validar_fuentes(mensaje["fuentes"], source)
        if fallo is not None:
            return rechazo(*fallo)
        fuentes = nombres

    return MensajeValido(
        event_id=event_id,
        updated_ms=updated_ms,
        updated=ms_a_datetime(updated_ms),
        source=source,
        mode=modo,
        ingested_at=ingested_at,
        sintetico=sintetico,
        mensaje=mensaje,
        fuentes=fuentes,
    )


def _validar_fuentes(fuentes, source: str) -> tuple[tuple[str, ...], tuple[str, str] | None]:
    """`(fuentes ordenadas, None)`, o `((), (motivo, detalle))` si la lista no cumple el contrato v2."""
    if not isinstance(fuentes, list) or not fuentes:
        return (), ("fuentes_invalidas", "fuentes debe ser una lista no vacía")
    nombres: list[str] = []
    principales: list[str] = []
    for entrada in fuentes:
        if not isinstance(entrada, dict) or sorted(entrada) != sorted(_CAMPOS_FUENTE):
            return (), ("fuentes_invalidas", "cada fuente lleva fuente, id, updated, principal y original")
        nombre, origen, updated = entrada["fuente"], entrada["id"], entrada["updated"]
        if not isinstance(nombre, str) or not _PATRON_SOURCE.match(nombre):
            return (), ("fuentes_invalidas", "fuentes[].fuente")
        if not isinstance(origen, str) or not origen:
            return (), ("fuentes_invalidas", "fuentes[].id")
        if not _es_entero(updated) or not 0 <= updated <= _UPDATED_MAXIMO_MS:
            return (), ("fuentes_invalidas", "fuentes[].updated")
        if not isinstance(entrada["principal"], bool) or not isinstance(entrada["original"], dict):
            return (), ("fuentes_invalidas", "fuentes[].principal u original")
        nombres.append(nombre)
        if entrada["principal"]:
            principales.append(nombre)
    if len(set(nombres)) != len(nombres):
        return (), ("fuentes_repetidas", "una fuente aparece dos veces")
    if principales != [source]:
        return (), ("principal_incoherente", "debe haber una sola principal y ser la de source")
    return tuple(sorted(nombres)), None


def construir_mensaje_v2(evento: dict, fuentes: list[dict], source: str, ingested_at: datetime) -> tuple[bytes, bytes]:
    """Clave y valor del evento fusionado (v2). Determinista: claves ordenadas y sin espacios,
    así la misma entrada produce los mismos bytes (la reentrega de la fusión es idéntica)."""
    event_id = evento.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("el evento no tiene id")
    cuerpo = {
        "schema_version": SCHEMA_VERSION_FUSION,
        "source": source,
        "ingested_at": iso_utc(ingested_at),
        "mode": "live",
        "event": evento,
        "fuentes": sorted(fuentes, key=lambda f: f["fuente"]),
    }
    valor = json.dumps(cuerpo, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return event_id.encode("utf-8"), valor.encode("utf-8")


def construir_mensaje(evento: dict, source: str, mode: str, ingested_at: datetime) -> tuple[bytes, bytes]:
    """Clave y valor del registro Kafka v1. El evento se incluye sin alterar."""
    event_id = evento.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("el evento no tiene id")
    cuerpo = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "ingested_at": iso_utc(ingested_at),
        "mode": mode,
        "event": evento,
    }
    valor = json.dumps(cuerpo, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return event_id.encode("utf-8"), valor
