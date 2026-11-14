"""Estado de la fusión en PostgreSQL (esquema `fusion`, data-model.md de 013).

Síncrono (psycopg 3): lo usa el driver de Spark dentro de `foreachBatch`, que no es asíncrono.
Cada lote es una transacción con cerrojo: se lee el estado, se decide, se escribe en Kafka y solo
entonces se confirma (research.md, «Garantía de entrega de la fusión»).
"""

import contextlib
import logging
import time
from collections.abc import Iterator, Sequence

import psycopg
from psycopg.types.json import Jsonb

from observatorio.common.config import AjustesPostgres
from observatorio.common.db import parametros_conexion
from observatorio.common.logging import registrar
from observatorio.common.retry import Backoff, esperas
from observatorio.fusion.emparejar import VENTANA_MS, Canonico, Resultado, id_canonico
from observatorio.fusion.normalizar import Descarte, Informe

_log = logging.getLogger("observatorio.fusion.estado")
_CERROJO = 13014  # un solo lote a la vez, aunque se arrancaran dos fusiones por error

DDL = (
    "SELECT pg_advisory_xact_lock(13013)",
    "CREATE SCHEMA IF NOT EXISTS fusion",
    """
    CREATE TABLE IF NOT EXISTS fusion.informe (
        fuente         text              NOT NULL,
        id_origen      text              NOT NULL CHECK (id_origen <> ''),
        updated_ms     bigint            NOT NULL CHECK (updated_ms >= 0),
        tiempo_ms      bigint            NOT NULL,
        latitud        double precision  NOT NULL,
        longitud       double precision  NOT NULL,
        profundidad    double precision,
        magnitud       double precision,
        tipo_magnitud  text,
        lugar          text,
        ingested_at    timestamptz       NOT NULL,
        original       jsonb             NOT NULL,
        canonico       text              NOT NULL,
        PRIMARY KEY (fuente, id_origen)
    )
    """,
    "CREATE INDEX IF NOT EXISTS informe_tiempo_idx ON fusion.informe (tiempo_ms)",
    "CREATE INDEX IF NOT EXISTS informe_canonico_idx ON fusion.informe (canonico)",
    """
    CREATE TABLE IF NOT EXISTS fusion.canonico (
        id                text         PRIMARY KEY,
        updated_ms        bigint       NOT NULL,
        firma             text         NOT NULL,
        fuente_principal  text         NOT NULL,
        actualizado_en    timestamptz  NOT NULL DEFAULT clock_timestamp()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fusion.descartes (
        id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        fuente        text,
        id_origen     text,
        motivo        text         NOT NULL,
        detalle       text,
        topic         text         NOT NULL,
        particion     integer      NOT NULL,
        offset_kafka  bigint       NOT NULL,
        visto_en      timestamptz  NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT descartes_posicion_unica UNIQUE (topic, particion, offset_kafka)
    )
    """,
)

# Siembra (FR-009): los eventos reales que ya estaban en la base antes de la fusión entran en su
# estado con su id, para que su pareja de EMSC se una a ellos en vez de duplicarlos. Solo versiones
# v1 de USGS (lo que escribía el productor antes de 013); idempotente.
SIEMBRA = (
    """
    INSERT INTO fusion.informe (fuente, id_origen, updated_ms, tiempo_ms, latitud, longitud, profundidad,
                                magnitud, tipo_magnitud, lugar, ingested_at, original, canonico)
    SELECT 'usgs', e.event_id,
           (extract(epoch FROM e.updated) * 1000)::bigint,
           (extract(epoch FROM e.ocurrencia) * 1000)::bigint,
           e.latitud, e.longitud, e.profundidad, e.magnitud,
           v.original -> 'event' -> 'properties' ->> 'magType',
           v.original -> 'event' -> 'properties' ->> 'place',
           e.ingested_at, v.original -> 'event', e.event_id
    FROM live.evento_actual e
    JOIN live.versiones_evento v ON v.event_id = e.event_id AND v.updated = e.updated
    WHERE NOT e.sintetico AND e.source = 'usgs' AND v.schema_version = 1
    ON CONFLICT DO NOTHING
    """,
    """
    INSERT INTO fusion.canonico (id, updated_ms, firma, fuente_principal)
    SELECT i.id_origen, i.updated_ms, 'usgs:' || i.id_origen || ':' || i.updated_ms, 'usgs'
    FROM fusion.informe i
    WHERE i.fuente = 'usgs' AND i.canonico = i.id_origen
      AND NOT EXISTS (SELECT 1 FROM fusion.canonico c WHERE c.id = i.canonico)
    ON CONFLICT DO NOTHING
    """,
)

_COLUMNAS = (
    "fuente, id_origen, updated_ms, tiempo_ms, latitud, longitud, profundidad, magnitud, "
    "tipo_magnitud, lugar, ingested_at, original, canonico"
)

# Informes de la ventana de tiempo del lote o ya conocidos por (fuente, id), y todos los miembros
# de los eventos a los que pertenecen: lo que `fusionar` necesita para decidir.
_CARGAR = f"""
    WITH lote(fuente, id_origen) AS (SELECT * FROM unnest(%s::text[], %s::text[])),
    eventos AS (
        SELECT canonico FROM fusion.informe WHERE tiempo_ms BETWEEN %s AND %s
        UNION
        SELECT i.canonico FROM fusion.informe i JOIN lote l USING (fuente, id_origen)
    )
    SELECT {_COLUMNAS} FROM fusion.informe WHERE canonico IN (SELECT canonico FROM eventos)
"""
_CANONICOS = "SELECT id, updated_ms, firma, fuente_principal FROM fusion.canonico WHERE id = ANY(%s)"
_GUARDAR_INFORME = f"""
    INSERT INTO fusion.informe ({_COLUMNAS})
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (fuente, id_origen) DO UPDATE SET
        updated_ms = EXCLUDED.updated_ms, tiempo_ms = EXCLUDED.tiempo_ms,
        latitud = EXCLUDED.latitud, longitud = EXCLUDED.longitud, profundidad = EXCLUDED.profundidad,
        magnitud = EXCLUDED.magnitud, tipo_magnitud = EXCLUDED.tipo_magnitud, lugar = EXCLUDED.lugar,
        ingested_at = EXCLUDED.ingested_at, original = EXCLUDED.original, canonico = EXCLUDED.canonico
"""
_GUARDAR_CANONICO = """
    INSERT INTO fusion.canonico (id, updated_ms, firma, fuente_principal) VALUES (%s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        updated_ms = EXCLUDED.updated_ms, firma = EXCLUDED.firma,
        fuente_principal = EXCLUDED.fuente_principal, actualizado_en = clock_timestamp()
"""
_DESCARTE = """
    INSERT INTO fusion.descartes (fuente, id_origen, motivo, detalle, topic, particion, offset_kafka)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (topic, particion, offset_kafka) DO NOTHING
"""


def _informe(fila) -> tuple[Informe, str]:
    (fuente, id_origen, updated_ms, tiempo_ms, latitud, longitud, profundidad, magnitud, tipo_magnitud,
     lugar, ingested_at, original, canonico) = fila
    informe = Informe(fuente, id_origen, updated_ms, tiempo_ms, latitud, longitud, profundidad, magnitud,
                      tipo_magnitud, lugar, ingested_at, original)
    return informe, canonico


class EstadoFusion:
    """Una conexión síncrona a PostgreSQL para el driver de Spark."""

    def __init__(self, ajustes: AjustesPostgres, backoff: Backoff):
        self._ajustes = ajustes
        self._backoff = backoff
        self._conn: psycopg.Connection | None = None

    def conectar(self) -> None:
        """Conecta con espera creciente (PostgreSQL puede no estar listo al arrancar)."""
        secuencia = esperas(self._backoff.inicial, self._backoff.factor, self._backoff.tope)
        intento = 0
        while True:
            try:
                self._conn = psycopg.connect(**parametros_conexion(self._ajustes))
                return
            except psycopg.OperationalError as exc:
                intento += 1
                espera = next(secuencia)
                registrar(_log, "reintento", dependency="postgres", attempt=intento, wait_s=espera,
                          reason=type(exc).__name__)
                time.sleep(espera)

    def cerrar(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def asegurar(self) -> dict[str, int]:
        """Crea el esquema si falta y siembra los eventos previos. Devuelve cuántos sembró."""
        conn = self._conexion()
        with conn.transaction():
            for sentencia in DDL:
                conn.execute(sentencia)
            informes = conn.execute(SIEMBRA[0]).rowcount
            canonicos = conn.execute(SIEMBRA[1]).rowcount
        return {"informes": informes, "canonicos": canonicos}

    @contextlib.contextmanager
    def lote(self) -> Iterator[psycopg.Connection]:
        """Transacción de un lote con cerrojo. Si algo falla dentro, no se confirma nada."""
        conn = self._conexion()
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_CERROJO,))
            yield conn

    def _conexion(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self.conectar()
        return self._conn


def cargar(conn, nuevos: Sequence[Informe]) -> tuple[list[tuple[Informe, str]], dict[str, Canonico]]:
    """Informes y eventos que necesita `fusionar` para este lote."""
    if not nuevos:
        return [], {}
    desde = min(i.tiempo_ms for i in nuevos) - VENTANA_MS
    hasta = max(i.tiempo_ms for i in nuevos) + VENTANA_MS
    fuentes = [i.fuente for i in nuevos]
    ids = [i.id_origen for i in nuevos]
    guardados = [_informe(f) for f in conn.execute(_CARGAR, (fuentes, ids, desde, hasta)).fetchall()]
    # Los eventos cargados y los ids que crearían los nuevos (para detectar una colisión).
    claves = sorted({c for _, c in guardados} | {id_canonico(i) for i in nuevos})
    canonicos = {
        fila[0]: Canonico(*fila) for fila in conn.execute(_CANONICOS, (claves,)).fetchall()
    }
    return guardados, canonicos


def guardar(conn, resultado: Resultado) -> None:
    if resultado.informes:
        with conn.cursor() as cur:
            cur.executemany(
                _GUARDAR_INFORME,
                [
                    (i.fuente, i.id_origen, i.updated_ms, i.tiempo_ms, i.latitud, i.longitud, i.profundidad,
                     i.magnitud, i.tipo_magnitud, i.lugar, i.ingested_at, Jsonb(i.original), canonico)
                    for i, canonico in resultado.informes
                ],
            )
    if resultado.canonicos:
        with conn.cursor() as cur:
            cur.executemany(
                _GUARDAR_CANONICO,
                [(c.id, c.updated_ms, c.firma, c.fuente_principal) for c in resultado.canonicos],
            )


def descartar(conn, descartes: Sequence[tuple[Descarte, str, int, int]]) -> None:
    if not descartes:
        return
    with conn.cursor() as cur:
        cur.executemany(
            _DESCARTE,
            [(d.fuente, d.id_origen, d.motivo, d.detalle, topic, particion, offset)
             for d, topic, particion, offset in descartes],
        )
