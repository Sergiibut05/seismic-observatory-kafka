"""Reglas de contenido de un mensaje ya válido por el contrato v1.

Lo que no se puede situar en el tiempo o en el mapa va a cuarentena.
Una magnitud o una profundidad ausentes se quedan en nulo: no se inventa un 0.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from observatorio.common.contrato import Rechazo
from observatorio.common.tiempo import ms_a_datetime

_TIEMPO_MAXIMO_MS = 4_102_444_800_000  # 2100-01-01 UTC, el mismo tope que `updated`


@dataclass(frozen=True)
class Contenido:
    ocurrencia_ms: int
    ocurrencia: datetime
    magnitud: float | None
    profundidad: float | None
    longitud: float
    latitud: float


def _entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _numero_finito(valor) -> float | None:
    """`None` si el hueco está vacío. El llamador distingue «ausente» de «inservible»."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    if not math.isfinite(numero):
        return None
    return numero


def evaluar(mensaje: dict) -> Contenido | Rechazo:
    """Devuelve el contenido utilizable o un rechazo con motivo de lista cerrada."""
    evento = mensaje.get("event") if isinstance(mensaje, dict) else None
    if not isinstance(evento, dict):
        return Rechazo("geometria_inutilizable", "event")
    geometria = evento.get("geometry")
    if not isinstance(geometria, dict) or geometria.get("type") != "Point":
        tipo = geometria.get("type") if isinstance(geometria, dict) else None
        return Rechazo("geometria_inutilizable", f"type={tipo}")
    coordenadas = geometria.get("coordinates")
    if not isinstance(coordenadas, list) or len(coordenadas) < 2:
        return Rechazo("coordenadas_invalidas", "se esperaban longitud y latitud")
    longitud = _numero_finito(coordenadas[0])
    latitud = _numero_finito(coordenadas[1])
    if longitud is None or latitud is None:
        return Rechazo("coordenadas_invalidas", "longitud o latitud no numérica")
    if not -180 <= longitud <= 180 or not -90 <= latitud <= 90:
        return Rechazo("coordenadas_fuera_de_rango", f"lon={longitud} lat={latitud}")

    profundidad = None
    if len(coordenadas) >= 3 and coordenadas[2] is not None:
        profundidad = _numero_finito(coordenadas[2])
        if profundidad is None:
            return Rechazo("profundidad_invalida", "coordinates[2]")

    propiedades = evento.get("properties")
    if not isinstance(propiedades, dict):
        return Rechazo("tiempo_invalido", "properties")
    tiempo = propiedades.get("time")
    if not _entero(tiempo) or not 0 <= tiempo <= _TIEMPO_MAXIMO_MS:
        return Rechazo("tiempo_invalido", "event.properties.time")

    magnitud = None
    if "mag" in propiedades and propiedades.get("mag") is not None:
        magnitud = _numero_finito(propiedades.get("mag"))
        if magnitud is None:
            return Rechazo("magnitud_invalida", "event.properties.mag")

    return Contenido(
        ocurrencia_ms=tiempo,
        ocurrencia=ms_a_datetime(tiempo),
        magnitud=magnitud,
        profundidad=profundidad,
        longitud=longitud,
        latitud=latitud,
    )
