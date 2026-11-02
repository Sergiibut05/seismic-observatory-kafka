"""SQL de versiones y cuarentena: una transacción por registro (R-09, R-15)."""

from psycopg import sql
from psycopg.types.json import Jsonb

from observatorio.common.contrato import MensajeValido
from observatorio.common.db import Database
from observatorio.consumer.decision import ESQUEMAS_DESTINO


def _esquema(esquema: str) -> sql.Identifier:
    # Lista cerrada: el nombre del esquema nunca llega como texto libre al SQL.
    if esquema not in ESQUEMAS_DESTINO.values():
        raise ValueError(f"esquema destino no permitido: {esquema!r}")
    return sql.Identifier(esquema)


async def guardar_version(db: Database, version: MensajeValido, registro, esquema: str) -> int:
    """Inserta la versión si no existía. Devuelve las filas insertadas (1) u omitidas (0).

    `processed_at` usa el valor por defecto de la base (`clock_timestamp()`).
    """
    consulta = sql.SQL(
        "INSERT INTO {}.versiones_evento "
        "(event_id, updated, schema_version, source, mode, sintetico, ingested_at, topic, particion, offset_kafka, original) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (event_id, updated) DO NOTHING"
    ).format(_esquema(esquema))
    parametros = (
        version.event_id,
        version.updated,
        version.mensaje["schema_version"],
        version.source,
        version.mode,
        version.sintetico,
        version.ingested_at,
        registro.topic,
        registro.partition,
        registro.offset,
        Jsonb(version.mensaje),
    )
    async with db.transaccion() as conn:
        cursor = await conn.execute(consulta, parametros)
        return cursor.rowcount


async def guardar_cuarentena(db: Database, motivo: str, detalle: str, registro) -> int:
    """Guarda el registro tal como llegó. Idempotente por posición Kafka (una reentrega no duplica)."""
    async with db.transaccion() as conn:
        cursor = await conn.execute(
            "INSERT INTO ingesta.cuarentena (motivo, detalle, topic, particion, offset_kafka, clave, original) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (topic, particion, offset_kafka) DO NOTHING",
            (motivo, detalle, registro.topic, registro.partition, registro.offset, registro.key, registro.value),
        )
        return cursor.rowcount
