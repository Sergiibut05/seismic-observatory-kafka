"""Evento sintético de la prueba de humo (R-11).

Por defecto es siempre el mismo (mismo `id` y `updated`): publicarlo de nuevo es un reenvío
exacto de la misma versión, lo que permite comprobar la idempotencia.
"""

from collections.abc import Callable
from datetime import datetime, timezone

from observatorio.common.contrato import construir_mensaje

SOURCE_SINTETICO = "synthetic-smoke"
_ID_BASE = "synthetic-smoke-0001"
UPDATED_MS = 1767225600000  # 2026-01-01T00:00:00Z


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def evento_sintetico(unico: bool = False, ahora: Callable[[], datetime] = _ahora_utc) -> dict:
    """Feature GeoJSON con la forma de USGS. `unico` sustituye el sufijo `0001` por la hora UTC."""
    event_id = _ID_BASE
    if unico:
        event_id = "synthetic-smoke-" + ahora().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "type": "Feature",
        "id": event_id,
        "properties": {
            "mag": 1.0,
            "place": "SINTÉTICO · prueba de humo (no es un terremoto real)",
            "time": UPDATED_MS,
            "updated": UPDATED_MS,
            "type": "earthquake",
            "title": "M 1.0 - SINTÉTICO · prueba de humo",
        },
        "geometry": {"type": "Point", "coordinates": [-3.7, 40.4, 10.0]},
    }


def mensaje_sintetico(unico: bool = False, ahora: Callable[[], datetime] = _ahora_utc) -> tuple[bytes, bytes]:
    """Clave y valor del registro Kafka v1 con el evento sintético."""
    return construir_mensaje(evento_sintetico(unico, ahora), SOURCE_SINTETICO, "live", ahora())
