"""Estado del sistema para `GET /status` (FR-023, R-19).

`armar_estado` es una función pura; las consultas están aparte para poder probarla sin base de datos.
"""

import logging
from datetime import datetime, timezone

from observatorio.common.db import Database, SinConexion
from observatorio.common.logging import registrar
from observatorio.common.retry import motivo_de
from observatorio.common.tiempo import iso_utc  # noqa: F401  (reexportado)

_log = logging.getLogger("observatorio.api")

# Una fila de `evento_actual` por evento: las revisiones no suman (R-19).
SQL_RECUENTOS = (
    "SELECT count(*) FILTER (WHERE NOT sintetico), "
    "count(*) FILTER (WHERE sintetico) "
    "FROM live.evento_actual"
)
SQL_ULTIMO_EVENTO = (
    "SELECT event_id, updated, source, sintetico, processed_at "
    "FROM live.evento_actual ORDER BY processed_at DESC LIMIT 1"
)


def armar_estado(
    conteos: tuple[int, int] | None,
    ultimo: tuple | None,
    db_ok: bool,
    ahora: datetime,
) -> dict:
    """Con la base caída todo dato de la base es `None` («no disponible»), nunca 0."""
    if not db_ok:
        return {
            "base_de_datos": "fallida",
            "eventos_reales": None,
            "eventos_sinteticos": None,
            "ultimo_evento": None,
            "generated_at": iso_utc(ahora),
        }
    reales, sinteticos = conteos if conteos is not None else (None, None)
    ultimo_evento = None
    if ultimo is not None:
        event_id, updated, source, sintetico, processed_at = ultimo
        ultimo_evento = {
            "event_id": event_id,
            "updated": iso_utc(updated),
            "source": source,
            "sintetico": bool(sintetico),
            "processed_at": iso_utc(processed_at),
        }
    return {
        "base_de_datos": "conectada",
        "eventos_reales": reales,
        "eventos_sinteticos": sinteticos,
        "ultimo_evento": ultimo_evento,
        "generated_at": iso_utc(ahora),
    }


async def consultar_estado(db: Database, logger: logging.Logger = _log) -> dict:
    """Consulta recuentos y último evento; ante cualquier fallo informa `fallida` (siempre 200)."""
    try:
        filas = await db.consultar(SQL_RECUENTOS, timeout=3)
        conteos = (filas[0][0], filas[0][1]) if filas else (0, 0)
        ultimas = await db.consultar(SQL_ULTIMO_EVENTO, timeout=3)
        ultimo = ultimas[0] if ultimas else None
        db_ok = True
    except SinConexion:
        conteos, ultimo, db_ok = None, None, False
    except Exception as exc:
        registrar(logger, "error", nivel="WARNING", component="postgres", reason=motivo_de(exc))
        conteos, ultimo, db_ok = None, None, False
    return armar_estado(conteos, ultimo, db_ok, datetime.now(timezone.utc))
