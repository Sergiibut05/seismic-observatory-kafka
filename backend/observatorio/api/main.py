"""API del observatorio: salud, estado y consultas analíticas de solo lectura (features 001 y 005).

Sin documentación pública (`/docs`, `/redoc`, `/openapi.json`), solo `GET` y `OPTIONS`, y errores con
cuerpo genérico: nada de SQL, rutas ni trazas.
"""

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from observatorio.api.estado import consultar_estado
from observatorio.api.filtros import FiltroInvalido
from observatorio.api.rutas import ServicioNoDisponible, crear_router
from observatorio.common.config import AjustesApi
from observatorio.common.db import Database
from observatorio.common.health import EstadoSalud
from observatorio.common.logging import registrar
from observatorio.common.supervisor import supervisar

_log = logging.getLogger("observatorio.api")


class SinCorsParaOrigenAjeno:
    """Quita toda cabecera `access-control-*` si el `Origin` no es uno de los permitidos (AC-9).

    El preflight de Starlette rechaza el origen ajeno con 400, pero deja `allow-methods` y
    `allow-headers`: aquí un origen no autorizado no recibe ninguna cabecera CORS.
    """

    def __init__(self, app, origenes: list[str]):
        self.app = app
        self.origenes = {origen.encode() for origen in origenes}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        origen = dict(scope["headers"]).get(b"origin")
        if origen is None or origen in self.origenes:
            await self.app(scope, receive, send)
            return

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                mensaje["headers"] = [
                    (k, v) for k, v in mensaje.get("headers", []) if not k.lower().startswith(b"access-control-")
                ]
            await send(mensaje)

        await self.app(scope, receive, enviar)


def crear_app(ajustes: AjustesApi, db: Database | None = None, estado: EstadoSalud | None = None) -> FastAPI:
    estado = estado or EstadoSalud(["postgres"])
    db = db or Database.desde_ajustes(ajustes.postgres, ajustes.backoff, estado=estado)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        registrar(_log, "iniciado", component="api")
        if not ajustes.cors_origen_netlify:
            registrar(
                _log, "info", nivel="WARNING", component="cors", aviso="CORS_ORIGEN_NETLIFY vacía: solo http://localhost:4200"
            )
        # La API no aborta si PostgreSQL no está: un supervisor conecta en segundo plano con backoff,
        # sondea la conexión y la recupera sola (`/health` 503 y `/status` «fallida» mientras tanto).
        async def abrir() -> Database:
            await db.conectar()
            return db

        async def sondear(base: Database) -> bool:
            return await base.sonda()

        conexion = asyncio.create_task(
            supervisar(
                abrir,
                sondear,
                "postgres",
                estado,
                ajustes,
                cerrar=Database.cerrar,
                logger=_log,
                registrar_listo=False,  # Database.conectar ya escribe su `result=listo`
            )
        )
        try:
            yield
        finally:
            conexion.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await conexion
            await db.cerrar()
            registrar(_log, "detenido", component="api")

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo_de_vida)

    @app.exception_handler(FiltroInvalido)
    async def filtro_invalido(peticion: Request, exc: FiltroInvalido) -> JSONResponse:
        # Se registra el nombre del parámetro, nunca su valor.
        registrar(
            _log, "rechazado", method=peticion.method, path=peticion.url.path, status=400, parametro=exc.parametro
        )
        return JSONResponse({"error": "parametro_invalido", "parametro": exc.parametro}, status_code=400)

    @app.exception_handler(ServicioNoDisponible)
    async def servicio_no_disponible(_: Request, __: ServicioNoDisponible) -> JSONResponse:
        return JSONResponse({"error": "servicio_no_disponible"}, status_code=503)

    @app.middleware("http")
    async def registro_de_acceso(peticion: Request, siguiente):
        inicio = time.perf_counter()
        try:
            respuesta = await siguiente(peticion)
        except Exception as exc:
            # Un fallo no previsto no filtra trazas: cuerpo genérico y detalle solo en el log. Se resuelve
            # aquí, dentro de CORS, para que el panel reciba el 500 y no un error de CORS.
            registrar(
                _log, "error", nivel="ERROR", component="api", method=peticion.method, path=peticion.url.path,
                reason=type(exc).__name__, exc_info=exc,
            )
            respuesta = JSONResponse({"error": "error_interno"}, status_code=500)
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

    # Se añade después del registro para quedar por fuera: atiende `OPTIONS` antes que nada y también
    # añade las cabeceras a los 400/503/500. Orígenes exactos, sin credenciales ni comodín (FR-011).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ajustes.origenes_cors,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["ngrok-skip-browser-warning"],
        allow_credentials=False,
        max_age=600,
    )
    app.add_middleware(SinCorsParaOrigenAjeno, origenes=ajustes.origenes_cors)

    @app.get("/health")
    async def health() -> JSONResponse:
        # Sin lista de componentes: es público; la causa va a los logs (R-12).
        if estado.sano:
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "unhealthy"}, status_code=503)

    @app.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(await consultar_estado(db, umbral_segundos=ajustes.datos_desactualizados_segundos))

    app.include_router(crear_router(db))
    return app
