"""Feed USGS: qué se publica, cuándo reintentar y cómo no guardar copias idénticas.

Funciones puras. La red y PostgreSQL están en `ciclo.py`.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE_USGS = "usgs"
URL_DEFECTO = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
_UPDATED_MAXIMO_MS = 4_102_444_800_000


class ErrorTransitorio(Exception):
    """429, 5xx, timeout o corte de red: se reintenta con espera progresiva."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class Exclusion:
    motivo: str
    event_id: str | None = None
    tipo: str | None = None


@dataclass(frozen=True)
class Clasificacion:
    publicar: tuple[dict, ...]
    omitidos: int
    exclusiones: tuple[Exclusion, ...]


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def es_transitorio(status: int) -> bool:
    return status == 429 or status >= 500


def clasificar(features, publicadas: set[tuple[str, int]]) -> Clasificacion:
    """Separa el feed en publicar, ya publicados y excluidos.

    `publicadas` son pares `(id, updated_ms)` con acuse. Dentro de la misma
    respuesta, una versión repetida se omite una sola vez y no se publica dos.
    """
    publicar: list[dict] = []
    exclusiones: list[Exclusion] = []
    omitidos = 0
    vistos: set[tuple[str, int]] = set()
    for crudo in features:
        if not isinstance(crudo, dict):
            exclusiones.append(Exclusion("feature_no_objeto"))
            continue
        event_id = crudo.get("id")
        if not isinstance(event_id, str) or not event_id:
            exclusiones.append(Exclusion("sin_id"))
            continue
        propiedades = crudo.get("properties")
        propiedades = propiedades if isinstance(propiedades, dict) else {}
        tipo = propiedades.get("type")
        if tipo != "earthquake":
            exclusiones.append(Exclusion("tipo_no_terremoto", event_id, tipo if isinstance(tipo, str) else None))
            continue
        updated = propiedades.get("updated")
        if not _es_entero(updated) or not 0 <= updated <= _UPDATED_MAXIMO_MS:
            exclusiones.append(Exclusion("updated_invalido", event_id))
            continue
        clave = (event_id, updated)
        if clave in publicadas or clave in vistos:
            omitidos += 1
            continue
        vistos.add(clave)
        publicar.append(crudo)
    return Clasificacion(tuple(publicar), omitidos, tuple(exclusiones))


def conservar_original(
    directorio: Path,
    contenido: bytes,
    ahora: datetime,
    retencion_horas: float,
) -> tuple[str, bool]:
    """Escribe el GeoJSON si su SHA-256 no es el de la copia más reciente.

    Devuelve `(sha256, copia_nueva)`. Borra los ficheros más viejos que la retención.
    """
    sha = hashlib.sha256(contenido).hexdigest()
    directorio.mkdir(parents=True, exist_ok=True)
    copias = sorted(directorio.glob("*.geojson"))
    copia_nueva = not copias or sha not in copias[-1].name
    if copia_nueva:
        nombre = ahora.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + sha + ".geojson"
        (directorio / nombre).write_bytes(contenido)
    limite = ahora.astimezone(timezone.utc) - timedelta(hours=retencion_horas)
    for copia in directorio.glob("*.geojson"):
        modificado = datetime.fromtimestamp(copia.stat().st_mtime, timezone.utc)
        if modificado < limite:
            copia.unlink()
    return sha, copia_nueva
