"""Lo propio de cada fuente: dónde se consulta, qué es un terremoto y cuál es la versión.

El ciclo del productor y el relleno son los mismos para todas las fuentes; solo cambia este
adaptador. Funciones puras (construyen URLs y leen respuestas; no hacen red).
"""

import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from observatorio.common.tiempo import iso_a_ms
from observatorio.producer.feed import URL_DEFECTO, Clasificacion, clasificar, tipo_usgs, version_usgs

USGS_FDSN = "https://earthquake.usgs.gov/fdsnws/event/1"
EMSC_FDSN = "https://www.seismicportal.eu/fdsnws/event/1"
# 24 h como el feed de USGS y 2 h de margen para lo que se publica con retraso.
VENTANA_DIRECTO_EMSC = timedelta(hours=26)
_TOPE_TIEMPO_MS = 4_102_444_800_000
_RECUENTO_EMSC = re.compile(rb"<Events>\s*(\d+)\s*</Events>")


def _instante(valor: datetime) -> str:
    """`2025-03-01T00:00:00` en UTC: sin zona, como piden los servicios FDSN."""
    return valor.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _magnitud(valor: float) -> str:
    return f"{valor:g}"


@dataclass(frozen=True)
class FuenteUsgs:
    """Feed de 24 h para el directo; FDSN para el relleno (rechaza más de 20.000 filas)."""

    feed_url: str = URL_DEFECTO
    base: str = USGS_FDSN
    nombre: str = "usgs"
    tope_consulta: int = 15_000

    def url_directo(self, ahora: datetime) -> str:
        return self.feed_url

    def url_consulta(self, desde: datetime, hasta: datetime, magnitud_min: float) -> str:
        return f"{self.base}/query?" + urllib.parse.urlencode(
            {
                "format": "geojson",
                "starttime": _instante(desde),
                "endtime": _instante(hasta),
                "minmagnitude": _magnitud(magnitud_min),
                "eventtype": "earthquake",
                "orderby": "time-asc",
            }
        )

    def url_recuento(self, desde: datetime, hasta: datetime, magnitud_min: float) -> str:
        return f"{self.base}/count?" + urllib.parse.urlencode(
            {
                "starttime": _instante(desde),
                "endtime": _instante(hasta),
                "minmagnitude": _magnitud(magnitud_min),
                "eventtype": "earthquake",
            }
        )

    def leer_recuento(self, cuerpo: bytes) -> int:
        return int(cuerpo.strip())

    def clasificar(self, features, publicadas: set[tuple[str, int]]) -> Clasificacion:
        return clasificar(features, publicadas, tipo_usgs, version_usgs)

    def version_de(self, evento: dict) -> int | None:
        return version_usgs(evento.get("properties") or {})


def tipo_emsc(propiedades: dict) -> tuple[bool, str | None]:
    """EMSC: `ke` es terremoto conocido; `se` (sospechoso) y `ue` (desconocido) no se publican."""
    tipo = propiedades.get("evtype")
    return tipo == "ke", tipo if isinstance(tipo, str) else None


def version_emsc(propiedades: dict) -> int | None:
    """`properties.lastupdate` (ISO 8601) en ms epoch."""
    valor = iso_a_ms(propiedades.get("lastupdate"))
    return valor if valor is not None and 0 <= valor <= _TOPE_TIEMPO_MS else None


@dataclass(frozen=True)
class FuenteEmsc:
    """FDSN de EMSC. Corta en ~10.000 filas sin avisar: el relleno parte por encima de 8.000."""

    base: str = EMSC_FDSN
    nombre: str = "emsc"
    tope_consulta: int = 8_000

    def url_directo(self, ahora: datetime) -> str:
        return f"{self.base}/query?" + urllib.parse.urlencode(
            {"format": "json", "start": _instante(ahora - VENTANA_DIRECTO_EMSC), "limit": 10_000}
        )

    def url_consulta(self, desde: datetime, hasta: datetime, magnitud_min: float) -> str:
        return f"{self.base}/query?" + urllib.parse.urlencode(
            {
                "format": "json",
                "start": _instante(desde),
                "end": _instante(hasta),
                "minmag": _magnitud(magnitud_min),
                "limit": 10_000,
                "orderby": "time-asc",
            }
        )

    def url_recuento(self, desde: datetime, hasta: datetime, magnitud_min: float) -> str:
        return f"{self.base}/count?" + urllib.parse.urlencode(
            {"start": _instante(desde), "end": _instante(hasta), "minmag": _magnitud(magnitud_min)}
        )

    def leer_recuento(self, cuerpo: bytes) -> int:
        coincidencia = _RECUENTO_EMSC.search(cuerpo)
        if coincidencia is None:
            raise ValueError("respuesta de recuento de EMSC sin <Events>")
        return int(coincidencia.group(1))

    def clasificar(self, features, publicadas: set[tuple[str, int]]) -> Clasificacion:
        return clasificar(features, publicadas, tipo_emsc, version_emsc)

    def version_de(self, evento: dict) -> int | None:
        return version_emsc(evento.get("properties") or {})


FUENTES_CONOCIDAS = ("usgs", "emsc")


def fuente_por_nombre(nombre: str, usgs_feed_url: str = URL_DEFECTO, emsc_base: str = EMSC_FDSN):
    if nombre == "usgs":
        return FuenteUsgs(feed_url=usgs_feed_url)
    if nombre == "emsc":
        return FuenteEmsc(base=emsc_base)
    raise ValueError(f"fuente desconocida: {nombre!r}")
