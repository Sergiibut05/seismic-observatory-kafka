"""De un mensaje de fuente (contrato v1) a un `Informe` comparable entre fuentes.

Cada fuente dice lo mismo de otra manera: USGS da los instantes en ms y la profundidad en la
geometría; EMSC da los instantes en ISO 8601 y la profundidad en `properties.depth` (en la
geometría viene con el signo cambiado). Aquí se traduce todo a una forma común.

Mismas reglas de calidad que el consumidor (`consumer/calidad.py`): lo que no se puede situar en
el tiempo o en el mapa se descarta con motivo; una magnitud o una profundidad ausentes quedan en
nulo, nunca en 0.
"""

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from observatorio.common.contrato import SCHEMA_VERSION
from observatorio.common.tiempo import iso_a_ms

FUENTES = ("emsc", "usgs")
_TIEMPO_MAXIMO_MS = 4_102_444_800_000  # 2100-01-01 UTC
_CAMPOS_RAIZ = ("schema_version", "source", "ingested_at", "mode", "event")


@dataclass(frozen=True)
class Informe:
    """Lo que una fuente dice de un terremoto, en forma común."""

    fuente: str
    id_origen: str
    updated_ms: int
    tiempo_ms: int
    latitud: float
    longitud: float
    profundidad: float | None
    magnitud: float | None
    tipo_magnitud: str | None
    lugar: str | None
    ingested_at: datetime
    original: dict


@dataclass(frozen=True)
class Descarte:
    motivo: str
    detalle: str = ""
    fuente: str | None = None
    id_origen: str | None = None


def _entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    return numero if math.isfinite(numero) else None


def _texto(valor) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def _ingested_at(texto) -> datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if instante.tzinfo is None or instante.utcoffset().total_seconds() != 0:
        return None
    return instante.astimezone(timezone.utc)


def fuente_del_topic(topic: str) -> str | None:
    """`eventos.emsc` → `emsc`. Solo las fuentes conocidas."""
    _, _, nombre = topic.rpartition(".")
    return nombre if nombre in FUENTES else None


def normalizar(clave: bytes | None, valor: bytes | str | None, topic: str) -> Informe | Descarte:
    """Valida el sobre v1 y traduce el evento de su fuente. El primer fallo decide el motivo."""
    fuente_topic = fuente_del_topic(topic)
    if fuente_topic is None:
        return Descarte("topic_desconocido", topic)
    if valor is None:
        return Descarte("valor_ausente", fuente=fuente_topic)
    try:
        texto = valor.decode("utf-8") if isinstance(valor, bytes) else valor
        mensaje = json.loads(texto)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        return Descarte("json_ilegible", type(exc).__name__, fuente_topic)
    if not isinstance(mensaje, dict) or sorted(mensaje) != sorted(_CAMPOS_RAIZ):
        return Descarte("campo_ausente", "se esperaba el sobre v1", fuente_topic)
    if mensaje["schema_version"] != SCHEMA_VERSION or not _entero(mensaje["schema_version"]):
        return Descarte("schema_version_no_soportada", str(mensaje["schema_version"]), fuente_topic)
    if mensaje["source"] != fuente_topic:
        return Descarte("fuente_no_corresponde_al_topic", f"source={mensaje['source']!r}", fuente_topic)
    if mensaje["mode"] != "live":
        return Descarte("mode_invalido", f"mode={mensaje['mode']!r}", fuente_topic)
    ingested_at = _ingested_at(mensaje["ingested_at"])
    if ingested_at is None:
        return Descarte("ingested_at_invalido", fuente=fuente_topic)

    evento = mensaje["event"]
    if not isinstance(evento, dict):
        return Descarte("evento_sin_id", "event", fuente_topic)
    id_origen = evento.get("id")
    if not isinstance(id_origen, str) or not id_origen:
        return Descarte("evento_sin_id", "event.id", fuente_topic)
    if clave is None or clave.decode("utf-8", errors="replace") != id_origen:
        return Descarte("clave_distinta_de_id", fuente=fuente_topic, id_origen=id_origen)

    traducir = _usgs if fuente_topic == "usgs" else _emsc
    return traducir(evento, id_origen, ingested_at)


def _descarte(motivo: str, detalle: str, fuente: str, id_origen: str) -> Descarte:
    return Descarte(motivo, detalle, fuente, id_origen)


def _situar(fuente, id_origen, longitud, latitud, tiempo_ms) -> Descarte | None:
    if longitud is None or latitud is None:
        return _descarte("coordenadas_invalidas", "longitud o latitud no numérica", fuente, id_origen)
    if not -180 <= longitud <= 180 or not -90 <= latitud <= 90:
        return _descarte("coordenadas_fuera_de_rango", f"lon={longitud} lat={latitud}", fuente, id_origen)
    if tiempo_ms is None or not 0 <= tiempo_ms <= _TIEMPO_MAXIMO_MS:
        return _descarte("tiempo_invalido", "hora de ocurrencia", fuente, id_origen)
    return None


def _usgs(evento: dict, id_origen: str, ingested_at: datetime) -> Informe | Descarte:
    propiedades = evento.get("properties")
    propiedades = propiedades if isinstance(propiedades, dict) else {}
    if propiedades.get("type") != "earthquake":
        return _descarte("tipo_no_terremoto", f"type={propiedades.get('type')!r}", "usgs", id_origen)
    updated = propiedades.get("updated")
    if not _entero(updated) or not 0 <= updated <= _TIEMPO_MAXIMO_MS:
        return _descarte("updated_invalido", "properties.updated", "usgs", id_origen)
    geometria = evento.get("geometry")
    coordenadas = geometria.get("coordinates") if isinstance(geometria, dict) else None
    if not isinstance(coordenadas, list) or len(coordenadas) < 2:
        return _descarte("coordenadas_invalidas", "se esperaban longitud y latitud", "usgs", id_origen)
    longitud, latitud = _numero(coordenadas[0]), _numero(coordenadas[1])
    tiempo = propiedades.get("time")
    fallo = _situar("usgs", id_origen, longitud, latitud, tiempo if _entero(tiempo) else None)
    if fallo:
        return fallo
    profundidad = None
    if len(coordenadas) >= 3 and coordenadas[2] is not None:
        profundidad = _numero(coordenadas[2])
        if profundidad is None:
            return _descarte("profundidad_invalida", "coordinates[2]", "usgs", id_origen)
    magnitud = None
    if propiedades.get("mag") is not None:
        magnitud = _numero(propiedades["mag"])
        if magnitud is None:
            return _descarte("magnitud_invalida", "properties.mag", "usgs", id_origen)
    return Informe(
        fuente="usgs",
        id_origen=id_origen,
        updated_ms=updated,
        tiempo_ms=tiempo,
        latitud=latitud,
        longitud=longitud,
        profundidad=profundidad,
        magnitud=magnitud,
        tipo_magnitud=_texto(propiedades.get("magType")),
        lugar=_texto(propiedades.get("place")),
        ingested_at=ingested_at,
        original=evento,
    )


def _emsc(evento: dict, id_origen: str, ingested_at: datetime) -> Informe | Descarte:
    propiedades = evento.get("properties")
    propiedades = propiedades if isinstance(propiedades, dict) else {}
    if propiedades.get("evtype") != "ke":
        return _descarte("tipo_no_terremoto", f"evtype={propiedades.get('evtype')!r}", "emsc", id_origen)
    updated = iso_a_ms(propiedades.get("lastupdate"))
    if updated is None or not 0 <= updated <= _TIEMPO_MAXIMO_MS:
        return _descarte("updated_invalido", "properties.lastupdate", "emsc", id_origen)
    # Coordenadas en `properties`; si faltan, las de la geometría (que traen lon y lat igual).
    longitud, latitud = _numero(propiedades.get("lon")), _numero(propiedades.get("lat"))
    if longitud is None or latitud is None:
        geometria = evento.get("geometry")
        coordenadas = geometria.get("coordinates") if isinstance(geometria, dict) else None
        if isinstance(coordenadas, list) and len(coordenadas) >= 2:
            longitud, latitud = _numero(coordenadas[0]), _numero(coordenadas[1])
    fallo = _situar("emsc", id_origen, longitud, latitud, iso_a_ms(propiedades.get("time")))
    if fallo:
        return fallo
    # `properties.depth` es positiva hacia abajo, como en USGS; la geometría la trae negativa.
    profundidad = None
    if propiedades.get("depth") is not None:
        profundidad = _numero(propiedades["depth"])
        if profundidad is None:
            return _descarte("profundidad_invalida", "properties.depth", "emsc", id_origen)
    magnitud = None
    if propiedades.get("mag") is not None:
        magnitud = _numero(propiedades["mag"])
        if magnitud is None:
            return _descarte("magnitud_invalida", "properties.mag", "emsc", id_origen)
    return Informe(
        fuente="emsc",
        id_origen=id_origen,
        updated_ms=updated,
        tiempo_ms=iso_a_ms(propiedades.get("time")),
        latitud=latitud,
        longitud=longitud,
        profundidad=profundidad,
        magnitud=magnitud,
        tipo_magnitud=_texto(propiedades.get("magtype")),
        lugar=_texto(propiedades.get("flynn_region")),
        ingested_at=ingested_at,
        original=evento,
    )
