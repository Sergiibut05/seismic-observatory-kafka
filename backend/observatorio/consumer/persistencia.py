"""SQL de versiones y cuarentena: una transacción por registro (R-09, R-15)."""

from psycopg import sql
from psycopg.types.json import Jsonb

from observatorio.common.catalogo import IndicePaises
from observatorio.common.contrato import MensajeValido
from observatorio.common.db import Database
from observatorio.consumer.calidad import Contenido, evaluar
from observatorio.consumer.decision import ESQUEMAS_DESTINO

# Solo sustituye la fila si la revisión entrante es estrictamente posterior.
COMPARACION_REVISION = "{}.evento_actual.updated < EXCLUDED.updated"


def _esquema(esquema: str) -> sql.Identifier:
    # Lista cerrada: el nombre del esquema nunca llega como texto libre al SQL.
    if esquema not in ESQUEMAS_DESTINO.values():
        raise ValueError(f"esquema destino no permitido: {esquema!r}")
    return sql.Identifier(esquema)


async def guardar_version(
    db: Database,
    version: MensajeValido,
    registro,
    esquema: str,
    contenido: Contenido | None = None,
    pais_codigo: str | None = None,
    pais_nombre: str | None = None,
) -> int:
    """Inserta la versión si no existía y, en la misma transacción, el estado actual.

    Devuelve las filas del historial (1 nueva, 0 ya existente). El estado actual se
    intenta igualmente: un reintento tras un fallo a medias tiene que poder corregirlo.
    """
    identificador = _esquema(esquema)
    consulta = sql.SQL(
        "INSERT INTO {}.versiones_evento "
        "(event_id, updated, schema_version, source, mode, sintetico, ingested_at, topic, particion, offset_kafka, original) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (event_id, updated) DO NOTHING"
    ).format(identificador)
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
        if contenido is not None:
            await _upsert_actual(
                conn,
                identificador,
                version.event_id,
                version.updated,
                contenido,
                pais_codigo,
                pais_nombre or "",
                version.source,
                version.mode,
                version.sintetico,
                version.ingested_at,
                None,
            )
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


def _upsert_sql(identificador: sql.Identifier) -> sql.Composed:
    return sql.SQL(
        """
        INSERT INTO {}.evento_actual (
            event_id, updated, ocurrencia, magnitud, profundidad, longitud, latitud,
            pais_codigo, pais_nombre, source, mode, sintetico, ingested_at, processed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, clock_timestamp()))
        ON CONFLICT (event_id) DO UPDATE SET
            updated = EXCLUDED.updated,
            ocurrencia = EXCLUDED.ocurrencia,
            magnitud = EXCLUDED.magnitud,
            profundidad = EXCLUDED.profundidad,
            longitud = EXCLUDED.longitud,
            latitud = EXCLUDED.latitud,
            pais_codigo = EXCLUDED.pais_codigo,
            pais_nombre = EXCLUDED.pais_nombre,
            source = EXCLUDED.source,
            mode = EXCLUDED.mode,
            sintetico = EXCLUDED.sintetico,
            ingested_at = EXCLUDED.ingested_at,
            processed_at = EXCLUDED.processed_at
        WHERE """
        + COMPARACION_REVISION
    ).format(identificador, identificador)


async def _upsert_actual(
    conn,
    identificador,
    event_id,
    updated,
    contenido: Contenido,
    pais_codigo,
    pais_nombre,
    source,
    mode,
    sintetico,
    ingested_at,
    processed_at,
) -> None:
    await conn.execute(
        _upsert_sql(identificador),
        (
            event_id,
            updated,
            contenido.ocurrencia,
            contenido.magnitud,
            contenido.profundidad,
            contenido.longitud,
            contenido.latitud,
            pais_codigo,
            pais_nombre,
            source,
            mode,
            sintetico,
            ingested_at,
            processed_at,
        ),
    )


_DDL = (
    """
    CREATE TABLE IF NOT EXISTS replay.versiones_evento (
        event_id        text         NOT NULL CHECK (event_id <> ''),
        updated         timestamptz  NOT NULL,
        schema_version  smallint     NOT NULL,
        source          text         NOT NULL,
        mode            text         NOT NULL DEFAULT 'replay' CHECK (mode = 'replay'),
        sintetico       boolean      NOT NULL,
        ingested_at     timestamptz  NOT NULL,
        processed_at    timestamptz  NOT NULL DEFAULT clock_timestamp(),
        topic           text         NOT NULL,
        particion       integer      NOT NULL,
        offset_kafka    bigint       NOT NULL,
        original        jsonb        NOT NULL,
        CONSTRAINT versiones_replay_pk PRIMARY KEY (event_id, updated),
        CONSTRAINT versiones_replay_sintetico_coherente CHECK (
            sintetico = (source LIKE 'synthetic-%')
            AND sintetico = (event_id LIKE 'synthetic-%'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingesta.pais (
        codigo      text PRIMARY KEY CHECK (codigo <> ''),
        nombre      text NOT NULL,
        continente  text,
        subregion   text
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS live.evento_actual (
        event_id      text             NOT NULL CHECK (event_id <> ''),
        updated       timestamptz      NOT NULL,
        ocurrencia    timestamptz      NOT NULL,
        magnitud      double precision,
        profundidad   double precision,
        longitud      double precision NOT NULL,
        latitud       double precision NOT NULL,
        pais_codigo   text,
        pais_nombre   text             NOT NULL,
        source        text             NOT NULL,
        mode          text             NOT NULL DEFAULT 'live' CHECK (mode = 'live'),
        sintetico     boolean          NOT NULL,
        ingested_at   timestamptz      NOT NULL,
        processed_at  timestamptz      NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT evento_actual_pk PRIMARY KEY (event_id),
        CONSTRAINT evento_actual_sintetico_coherente CHECK (
            sintetico = (source LIKE 'synthetic-%')
            AND sintetico = (event_id LIKE 'synthetic-%')),
        CONSTRAINT evento_actual_pais_fk FOREIGN KEY (pais_codigo) REFERENCES ingesta.pais (codigo)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay.evento_actual (
        event_id      text             NOT NULL CHECK (event_id <> ''),
        updated       timestamptz      NOT NULL,
        ocurrencia    timestamptz      NOT NULL,
        magnitud      double precision,
        profundidad   double precision,
        longitud      double precision NOT NULL,
        latitud       double precision NOT NULL,
        pais_codigo   text,
        pais_nombre   text             NOT NULL,
        source        text             NOT NULL,
        mode          text             NOT NULL DEFAULT 'replay' CHECK (mode = 'replay'),
        sintetico     boolean          NOT NULL,
        ingested_at   timestamptz      NOT NULL,
        processed_at  timestamptz      NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT evento_replay_pk PRIMARY KEY (event_id),
        CONSTRAINT evento_replay_sintetico_coherente CHECK (
            sintetico = (source LIKE 'synthetic-%')
            AND sintetico = (event_id LIKE 'synthetic-%')),
        CONSTRAINT evento_replay_pais_fk FOREIGN KEY (pais_codigo) REFERENCES ingesta.pais (codigo)
    )
    """,
    "CREATE INDEX IF NOT EXISTS evento_actual_pais_ocurrencia_idx ON live.evento_actual (pais_nombre, ocurrencia)",
    "CREATE INDEX IF NOT EXISTS evento_replay_pais_ocurrencia_idx ON replay.evento_actual (pais_nombre, ocurrencia)",
    "INSERT INTO ingesta.version_esquema (version, nombre) VALUES (4, 'estado_actual') ON CONFLICT (version) DO NOTHING",
)

_UPSERT_PAIS = (
    "INSERT INTO ingesta.pais (codigo, nombre, continente, subregion) VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre, "
    "continente = EXCLUDED.continente, subregion = EXCLUDED.subregion"
)


async def asegurar_modelo(db: Database, indice: IndicePaises | None) -> dict[str, int]:
    """Crea las tablas que un volumen antiguo no tiene y rellena el estado actual."""
    async with db.transaccion(timeout=60) as conn:
        for sentencia in _DDL:
            await conn.execute(sentencia)
        if indice is not None:
            for fila in indice.filas():
                await conn.execute(_UPSERT_PAIS, fila)
    if indice is None:
        return {}
    return {
        "live": await rellenar_estado(db, indice, "live"),
        "replay": await rellenar_estado(db, indice, "replay"),
    }


async def rellenar_estado(db: Database, indice: IndicePaises, esquema: str) -> int:
    """Proyecta las versiones ya guardadas. Una revisión vieja no pisa a una más nueva."""
    identificador = _esquema(esquema)
    filas = await db.consultar(
        sql.SQL(
            "SELECT event_id, updated, source, mode, sintetico, ingested_at, processed_at, original "
            "FROM {}.versiones_evento ORDER BY updated"
        ).format(identificador),
        timeout=30,
    )
    async with db.transaccion(timeout=120) as conn:
        for event_id, updated, source, mode, sintetico, ingested_at, processed_at, original in filas:
            contenido = evaluar(original)
            if not isinstance(contenido, Contenido):
                continue
            codigo, nombre = indice.asignar(contenido.longitud, contenido.latitud)
            await _upsert_actual(
                conn,
                identificador,
                event_id,
                updated,
                contenido,
                codigo,
                nombre,
                source,
                mode,
                sintetico,
                ingested_at,
                processed_at,
            )
    return len(filas)
