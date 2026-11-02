"""Una pasada del feed: descargar, guardar el original, publicar lo nuevo y apuntarlo."""

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
    SOURCE_USGS,
    Clasificacion,
    ErrorTransitorio,
    clasificar,
    conservar_original,
    es_transitorio,
)

_log = logging.getLogger("observatorio.producer.ciclo")

_SQL_TABLAS = (
    """
    CREATE TABLE IF NOT EXISTS ingesta.publicadas (
        event_id text NOT NULL CHECK (event_id <> ''),
        updated_ms bigint NOT NULL CHECK (updated_ms >= 0),
        publicada_en timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY (event_id, updated_ms)
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
)

_SQL_PUBLICADAS = "SELECT event_id, updated_ms FROM ingesta.publicadas"
_SQL_MARCAR = (
    "INSERT INTO ingesta.publicadas (event_id, updated_ms) VALUES (%s, %s) ON CONFLICT DO NOTHING"
)
_SQL_CONSULTA = """
    INSERT INTO ingesta.consultas
        (url, http_status, bytes, sha256, features, publicados, omitidos, excluidos, copia_nueva, error)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""
_SQL_EXCLUSION = (
    "INSERT INTO ingesta.exclusiones (consulta_id, event_id, tipo, motivo) VALUES (%s, %s, %s, %s)"
)


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


async def _anotar_consulta(db, url, **campos) -> int | None:
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
    )
    async with db.transaccion() as conn:
        cursor = await conn.execute(_SQL_CONSULTA, valores)
        fila = await cursor.fetchone()
    return fila[0] if fila else None


async def una_pasada(ajustes, productor, db, descargar_feed=descargar, ahora: datetime | None = None) -> Clasificacion:
    """Una consulta completa. Lanza `ErrorTransitorio` si hay que reintentar ya.

    Un JSON ilegible o un HTTP definitivo se registran y la pasada termina sin
    tocar `ingesta.publicadas`.
    """
    ahora = ahora or datetime.now(timezone.utc)
    url = ajustes.usgs_feed_url
    try:
        status, cuerpo = await asyncio.to_thread(descargar_feed, url, ajustes.http_timeout_seconds)
    except ErrorTransitorio as exc:
        await _anotar_consulta(db, url, error=exc.motivo)
        raise

    if es_transitorio(status):
        await _anotar_consulta(db, url, http_status=status, bytes=len(cuerpo), error=f"http_{status}")
        raise ErrorTransitorio(f"http_{status}")
    if status != 200:
        await _anotar_consulta(db, url, http_status=status, bytes=len(cuerpo), error=f"http_{status}")
        registrar(_log, "error", nivel="WARNING", component="usgs", reason=f"http_{status}")
        return Clasificacion((), 0, ())

    try:
        documento = json.loads(cuerpo)
        features = documento["features"]
        if not isinstance(features, list):
            raise TypeError("features no es una lista")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        await _anotar_consulta(db, url, http_status=status, bytes=len(cuerpo), error="json")
        registrar(_log, "error", nivel="WARNING", component="usgs", reason="json", detalle=type(exc).__name__)
        return Clasificacion((), 0, ())

    sha, copia_nueva = conservar_original(
        Path(ajustes.feed_dir), cuerpo, ahora, ajustes.feed_retention_hours
    )
    filas = await db.consultar(_SQL_PUBLICADAS)
    clasificacion = clasificar(features, {(fila[0], fila[1]) for fila in filas})

    publicados = 0
    for evento in clasificacion.publicar:
        clave, valor = construir_mensaje(evento, SOURCE_USGS, "live", ahora)
        await productor.send_and_wait(ajustes.topic_live, value=valor, key=clave)
        updated_ms = evento["properties"]["updated"]
        async with db.transaccion() as conn:
            await conn.execute(_SQL_MARCAR, (evento["id"], updated_ms))
        registrar(_log, "publicado", event_id=evento["id"], updated=updated_ms, source=SOURCE_USGS)
        publicados += 1

    consulta_id = await _anotar_consulta(
        db,
        url,
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
                    (consulta_id, exclusion.event_id, exclusion.tipo, exclusion.motivo),
                )
    if clasificacion.omitidos:
        registrar(_log, "omitido", component="usgs", omitidos=clasificacion.omitidos)
    registrar(
        _log,
        "listo",
        component="usgs",
        features=len(features),
        publicados=publicados,
        excluidos=len(clasificacion.exclusiones),
        copia_nueva=copia_nueva,
    )
    return clasificacion
