"""API del observatorio (feature 001): solo `GET /health` y `GET /status`, sin documentación pública."""

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from observatorio.api.estado import consultar_estado
from observatorio.common.config import AjustesApi
from observatorio.common.db import Database
from observatorio.common.health import EstadoSalud
from observatorio.common.logging import registrar

_log = logging.getLogger("observatorio.api")


def crear_app(ajustes: AjustesApi, db: Database | None = None, estado: EstadoSalud | None = None) -> FastAPI:
    estado = estado or EstadoSalud(["postgres"])
    db = db or Database.desde_ajustes(ajustes.postgres, ajustes.backoff, estado=estado)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        registrar(_log, "iniciado", component="api")
        # La API no aborta si PostgreSQL no está: conecta en segundo plano con backoff.
        conexion = asyncio.create_task(db.conectar())
        try:
            yield
        finally:
            conexion.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await conexion
            await db.cerrar()
            registrar(_log, "detenido", component="api")

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo_de_vida)

    @app.middleware("http")
    async def registro_de_acceso(peticion: Request, siguiente):
        inicio = time.perf_counter()
        respuesta = await siguiente(peticion)
        # /health lo consulta Compose cada pocos segundos: va a DEBUG para no inundar el log.
        registrar(
            _log,
            "info",
            nivel="DEBUG" if peticion.url.path == "/health" else "INFO",
            method=peticion.method,
            path=peticion.url.path,
            status=respuesta.status_code,
            ms=round((time.perf_counter() - inicio) * 1000),
        )
        return respuesta

    @app.get("/health")
    async def health() -> JSONResponse:
        # Sin lista de componentes: es público; la causa va a los logs (R-12).
        if estado.sano:
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "unhealthy"}, status_code=503)

    @app.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(await consultar_estado(db))

    return app
