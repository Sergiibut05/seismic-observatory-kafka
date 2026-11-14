"""Una pasada de una fuente: descargar, guardar el original, publicar lo nuevo y apuntarlo.

Igual para todas las fuentes; lo propio de cada una está en `fuentes.py` (013).
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from observatorio.common.contrato import construir_mensaje
from observatorio.common.logging import registrar
from observatorio.producer.feed import (
    Clasificacion,
    ErrorTransitorio,
    conservar_original,
    es_transitorio,
)
from observatorio.producer.fuentes import fuente_por_nombre

_log = logging.getLogger("observatorio.producer.ciclo")

_SQL_TABLAS = (
    # Los dos productores arrancan a la vez: el cerrojo evita que migren la tabla en paralelo.
    "SELECT pg_advisory_xact_lock(13013)",
    """
    CREATE TABLE IF NOT EXISTS ingesta.publicadas (
        event_id text NOT NULL CHECK (event_id <> ''),
        updated_ms bigint NOT NULL CHECK (updated_ms >= 0),
        publicada_en timestamptz NOT NULL DEFAULT clock_timestamp(),
        fuente text NOT NULL DEFAULT 'usgs',
        PRIMARY KEY (fuente, event_id, updated_ms)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingesta.consultas (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        url text NOT NULL,
        acabada_en timestamptz NOT NULL DEFAULT clock_timestamp(),
        http_status integer,
        bytes integer,
        sha256 text,
        features integer,
        publicados integer,
        omitidos integer,
        excluidos integer,
        copia_nueva boolean,
        error text
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingesta.exclusiones (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        consulta_id bigint,
        event_id text,
        tipo text,
        motivo text NOT NULL,
        visto_en timestamptz NOT NULL DEFAULT clock_timestamp()
    )
    """,
    """
    INSERT INTO ingesta.version_esquema (version, nombre)
    VALUES (2, 'ingesta_live') ON CONFLICT (version) DO NOTHING
    """,
    # 013 (db/init/006_multifuente.sql): la fuente en las tablas de ingesta de un volumen antiguo.
    "ALTER TABLE ingesta.publicadas ADD COLUMN IF NOT EXISTS fuente text NOT NULL DEFAULT 'usgs'",
    "ALTER TABLE ingesta.consultas ADD COLUMN IF NOT EXISTS fuente text NOT NULL DEFAULT 'usgs'",
    "ALTER TABLE ingesta.exclusiones ADD COLUMN IF NOT EXISTS fuente text NOT NULL DEFAULT 'usgs'",
    """
    DO $$
    DECLARE pk text;
    BEGIN
        SELECT conname INTO pk FROM pg_constraint
        WHERE conrelid = 'ingesta.publicadas'::regclass AND contype = 'p' AND array_length(conkey, 1) = 2;
        IF pk IS NOT NULL THEN
            EXECUTE format('ALTER TABLE ingesta.publicadas DROP CONSTRAINT %I', pk);
            ALTER TABLE ingesta.publicadas ADD PRIMARY KEY (fuente, event_id, updated_ms);
        END IF;
    END $$
    """,
    """
    INSERT INTO ingesta.version_esquema (version, nombre)
    VALUES (6, 'multifuente') ON CONFLICT (version) DO NOTHING
    """,
)

# Solo los ids de esta respuesta: con el relleno, la tabla tiene cientos de miles de filas.
_SQL_PUBLICADAS = "SELECT event_id, updated_ms FROM ingesta.publicadas WHERE fuente = %s AND event_id = ANY(%s)"
_SQL_MARCAR = (
    "INSERT INTO ingesta.publicadas (event_id, updated_ms, fuente) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
)
_SQL_CONSULTA = """
    INSERT INTO ingesta.consultas
        (url, http_status, bytes, sha256, features, publicados, omitidos, excluidos, copia_nueva, error, fuente)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""
_SQL_EXCLUSION = (
    "INSERT INTO ingesta.exclusiones (consulta_id, event_id, tipo, motivo, fuente) VALUES (%s, %s, %s, %s, %s)"
)
# FDSN responde 204 sin cuerpo cuando no hay eventos (EMSC lo hace): no es un error.
SIN_DATOS = 204


def descargar(url: str, timeout: float) -> tuple[int, bytes]:
    """GET síncrono. 429/5xx/red lanzan `ErrorTransitorio`; el resto devuelve el status."""
    peticion = Request(url, headers={"User-Agent": "seismic-observatory/1.0", "Accept": "application/json"})
    try:
        with urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.status, respuesta.read()
    except HTTPError as exc:
        if es_transitorio(exc.code):
            raise ErrorTransitorio(f"http_{exc.code}") from exc
        return exc.code, exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise ErrorTransitorio("red") from exc


async def asegurar_tablas(db) -> None:
    async with db.transaccion() as conn:
        for sentencia in _SQL_TABLAS:
            await conn.execute(sentencia)


async def _anotar_consulta(db, url, fuente: str = "usgs", **campos) -> int | None:
    valores = (
        url,
        campos.get("http_status"),
        campos.get("bytes"),
        campos.get("sha256"),
        campos.get("features"),
        campos.get("publicados"),
        campos.get("omitidos"),
        campos.get("excluidos"),
        campos.get("copia_nueva"),
        campos.get("error"),
        fuente,
    )
    async with db.transaccion() as conn:
        cursor = await conn.execute(_SQL_CONSULTA, valores)
        fila = await cursor.fetchone()
    return fila[0] if fila else None


async def una_pasada(
    ajustes, productor, db, descargar_feed=descargar, ahora: datetime | None = None, fuente=None
) -> Clasificacion:
    """Una consulta completa de la fuente de `ajustes`. Lanza `ErrorTransitorio` si hay que reintentar ya.

    Un JSON ilegible o un HTTP definitivo se registran y la pasada termina sin
    tocar `ingesta.publicadas`.
    """
    ahora = ahora or datetime.now(timezone.utc)
    fuente = fuente or fuente_por_nombre(ajustes.fuente, ajustes.usgs_feed_url, ajustes.emsc_url_base)
    nombre = fuente.nombre
    url = fuente.url_directo(ahora)
    try:
        status, cuerpo = await asyncio.to_thread(descargar_feed, url, ajustes.http_timeout_seconds)
    except ErrorTransitorio as exc:
        await _anotar_consulta(db, url, nombre, error=exc.motivo)
        raise

    if es_transitorio(status):
        await _anotar_consulta(db, url, nombre, http_status=status, bytes=len(cuerpo), error=f"http_{status}")
        raise ErrorTransitorio(f"http_{status}")
    if status == SIN_DATOS:
        await _anotar_consulta(db, url, nombre, http_status=status, bytes=0, features=0, publicados=0)
        registrar(_log, "listo", component=nombre, features=0, publicados=0, excluidos=0, copia_nueva=False)
        return Clasificacion((), 0, ())
    if status != 200:
        await _anotar_consulta(db, url, nombre, http_status=status, bytes=len(cuerpo), error=f"http_{status}")
        registrar(_log, "error", nivel="WARNING", component=nombre, reason=f"http_{status}")
        return Clasificacion((), 0, ())

    try:
        documento = json.loads(cuerpo)
        features = documento["features"]
        if not isinstance(features, list):
            raise TypeError("features no es una lista")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        await _anotar_consulta(db, url, nombre, http_status=status, bytes=len(cuerpo), error="json")
        registrar(_log, "error", nivel="WARNING", component=nombre, reason="json", detalle=type(exc).__name__)
        return Clasificacion((), 0, ())

    sha, copia_nueva = conservar_original(
        Path(ajustes.feed_dir), cuerpo, ahora, ajustes.feed_retention_hours
    )
    ids = sorted({f["id"] for f in features if isinstance(f, dict) and isinstance(f.get("id"), str)})
    filas = await db.consultar(_SQL_PUBLICADAS, (nombre, ids)) if ids else []
    clasificacion = fuente.clasificar(features, {(fila[0], fila[1]) for fila in filas})

    publicados = 0
    for evento in clasificacion.publicar:
        clave, valor = construir_mensaje(evento, nombre, "live", ahora)
        await productor.send_and_wait(ajustes.topic_fuente, value=valor, key=clave)
        version = fuente.version_de(evento)
        async with db.transaccion() as conn:
            await conn.execute(_SQL_MARCAR, (evento["id"], version, nombre))
        registrar(_log, "publicado", event_id=evento["id"], updated=version, source=nombre)
        publicados += 1

    consulta_id = await _anotar_consulta(
        db,
        url,
        nombre,
        http_status=status,
        bytes=len(cuerpo),
        sha256=sha,
        features=len(features),
        publicados=publicados,
        omitidos=clasificacion.omitidos,
        excluidos=len(clasificacion.exclusiones),
        copia_nueva=copia_nueva,
    )
    if clasificacion.exclusiones:
        async with db.transaccion() as conn:
            for exclusion in clasificacion.exclusiones:
                await conn.execute(
                    _SQL_EXCLUSION,
                    (consulta_id, exclusion.event_id, exclusion.tipo, exclusion.motivo, nombre),
                )
    if clasificacion.omitidos:
        registrar(_log, "omitido", component=nombre, omitidos=clasificacion.omitidos)
    registrar(
        _log,
        "listo",
        component=nombre,
        features=len(features),
        publicados=publicados,
        excluidos=len(clasificacion.exclusiones),
        copia_nueva=copia_nueva,
    )
    return clasificacion
