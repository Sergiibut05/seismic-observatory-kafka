"""Endpoints analíticos de solo lectura (feature 005). Todos `GET`; el resto de métodos da 405.

Cada manejador valida con `filtros`, consulta con `consultas` (SQL parametrizado) y da forma a la
respuesta con `calculos`. Un fallo de la base se traduce a `ServicioNoDisponible` (503 genérico):
nunca una lista vacía ni un 0 en su lugar.
"""

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from observatorio.api import consultas as sql
from observatorio.api.calculos import (
    BORDES_MAGNITUD,
    BORDES_PROFUNDIDAD,
    MAPA_TOPE,
    armar_intervalos,
    comparar,
    geojson_mapa,
    rellenar_horas,
)
from observatorio.api.filtros import (
    PARAMS_COMPARACION,
    PARAMS_FILTRO,
    PARAMS_LISTA,
    Filtros,
    construir_where,
    leer_filtros,
    leer_paginacion,
    leer_ventana,
    valores_unicos,
)
from observatorio.common.catalogo import SIN_PAIS
from observatorio.common.db import Database, SinConexion
from observatorio.common.logging import registrar
from observatorio.common.retry import motivo_de
from observatorio.common.tiempo import iso_utc

_log = logging.getLogger("observatorio.api")

# El objetivo es ≤ 3 s: un timeout de 5 s es un fallo real, no un falso positivo (plan, decisión 3).
CONSULTA_TIMEOUT = 5.0
MAGNITUD_MINIMA_COMPARACION = 4.0
SIN_SUBREGION = "Sin subregión"
AVISO_COMPARACION = (
    "El último periodo puede estar incompleto: USGS publica con retraso y revisa los eventos después."
)
AVISO_NO_CARGADO = " El histórico de 2025 no está cargado: no hay media ni cociente."


class ServicioNoDisponible(Exception):
    """La base de datos no puede responder ahora (sin conexión, error o tiempo agotado)."""


def ahora_utc() -> datetime:
    """Instante actual en UTC con precisión de milisegundos (lo que se muestra es lo que se consultó)."""
    ahora = datetime.now(timezone.utc)
    return ahora.replace(microsecond=ahora.microsecond // 1000 * 1000)


async def ejecutar(
    db: Database, consulta: str, params=None, timeout: float = CONSULTA_TIMEOUT, logger: logging.Logger = _log
) -> list[tuple]:
    """Ejecuta un `SELECT`; cualquier fallo de la base pasa a `ServicioNoDisponible` sin detalles."""
    try:
        return await db.consultar(consulta, params, timeout=timeout)
    except SinConexion:
        raise ServicioNoDisponible from None
    except (psycopg.Error, TimeoutError, OSError) as exc:
        registrar(logger, "error", nivel="WARNING", component="postgres", reason=motivo_de(exc))
        raise ServicioNoDisponible from None


def _leer(peticion: Request, permitidos: frozenset[str]) -> tuple[dict[str, str], Filtros]:
    valores = valores_unicos(peticion.query_params.multi_items(), permitidos)
    return valores, leer_filtros(valores)


def crear_router(db: Database, reloj: Callable[[], datetime] = ahora_utc) -> APIRouter:
    router = APIRouter()

    @router.get("/eventos")
    async def eventos(peticion: Request) -> JSONResponse:
        valores = valores_unicos(peticion.query_params.multi_items(), PARAMS_LISTA)
        filtros = leer_filtros(valores)
        limite, desplazamiento = leer_paginacion(valores)
        donde, params = construir_where(filtros)
        total = (await ejecutar(db, sql.con_where(sql.SQL_TOTAL, donde), params))[0][0]
        filas = await ejecutar(db, sql.con_where(sql.SQL_LISTA, donde), [*params, limite, desplazamiento])
        return JSONResponse(
            {
                "eventos": [
                    {
                        "event_id": event_id,
                        "ocurrencia": iso_utc(ocurrencia),
                        "updated": iso_utc(updated),
                        "magnitud": magnitud,
                        "profundidad": profundidad,
                        "longitud": longitud,
                        "latitud": latitud,
                        "pais_codigo": pais_codigo,
                        "pais_nombre": pais_nombre,
                        "subregion": subregion,
                        "sintetico": bool(sintetico),
                    }
                    for (
                        event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud,
                        pais_codigo, pais_nombre, subregion, sintetico,
                    ) in filas
                ],
                "total": total,
                "limite": limite,
                "desplazamiento": desplazamiento,
            }
        )

    @router.get("/eventos/mapa")
    async def mapa(peticion: Request) -> JSONResponse:
        _, filtros = _leer(peticion, PARAMS_FILTRO)
        donde, params = construir_where(filtros)
        generado = reloj()
        total = (await ejecutar(db, sql.con_where(sql.SQL_TOTAL, donde), params))[0][0]
        filas = await ejecutar(db, sql.con_where(sql.SQL_MAPA, donde), [*params, MAPA_TOPE])
        return JSONResponse(geojson_mapa(filas, total, MAPA_TOPE, generado))

    @router.get("/recuentos/pais")
    async def recuentos_pais(peticion: Request) -> JSONResponse:
        _, filtros = _leer(peticion, PARAMS_FILTRO)
        donde, params = construir_where(filtros)
        filas = await ejecutar(db, sql.con_where(sql.SQL_RECUENTO_PAIS, donde), params)
        categorias = [{"codigo": codigo, "nombre": nombre, "recuento": n} for codigo, nombre, n in filas]
        return JSONResponse({"total": sum(c["recuento"] for c in categorias), "categorias": categorias})

    @router.get("/recuentos/subregion")
    async def recuentos_subregion(peticion: Request) -> JSONResponse:
        _, filtros = _leer(peticion, PARAMS_FILTRO)
        donde, params = construir_where(filtros)
        filas = await ejecutar(db, sql.con_where(sql.SQL_RECUENTO_SUBREGION, donde), params)
        acumulado: dict[str, int] = {}
        for subregion, sin_pais, n in filas:
            nombre = SIN_PAIS if sin_pais else (subregion or SIN_SUBREGION)
            acumulado[nombre] = acumulado.get(nombre, 0) + n
        categorias = [
            {"nombre": nombre, "recuento": n}
            for nombre, n in sorted(acumulado.items(), key=lambda par: (-par[1], par[0]))
        ]
        return JSONResponse({"total": sum(acumulado.values()), "categorias": categorias})

    @router.get("/recuentos/hora")
    async def recuentos_hora(peticion: Request) -> JSONResponse:
        _, filtros = _leer(peticion, PARAMS_FILTRO)
        filtros = leer_ventana(filtros, reloj())
        donde, params = construir_where(filtros)
        filas = await ejecutar(db, sql.con_where(sql.SQL_RECUENTO_HORA, donde), params)
        ventanas = rellenar_horas(filas, filtros.desde, filtros.hasta)
        return JSONResponse(
            {
                "desde": iso_utc(filtros.desde),
                "hasta": iso_utc(filtros.hasta),
                "total": sum(v["recuento"] for v in ventanas),
                "ventanas": ventanas,
            }
        )

    async def _distribucion(peticion: Request, consulta: str, bordes: tuple[int, ...], unidad: str) -> JSONResponse:
        _, filtros = _leer(peticion, PARAMS_FILTRO)
        donde, params = construir_where(filtros)
        filas = await ejecutar(db, sql.con_where(consulta, donde), params)
        intervalos, sin_valor, total = armar_intervalos(filas, bordes)
        return JSONResponse({"unidad": unidad, "total": total, "sin_valor": sin_valor, "intervalos": intervalos})

    @router.get("/distribuciones/magnitud")
    async def distribucion_magnitud(peticion: Request) -> JSONResponse:
        return await _distribucion(peticion, sql.SQL_DISTRIBUCION_MAGNITUD, BORDES_MAGNITUD, "magnitud")

    @router.get("/distribuciones/profundidad")
    async def distribucion_profundidad(peticion: Request) -> JSONResponse:
        return await _distribucion(peticion, sql.SQL_DISTRIBUCION_PROFUNDIDAD, BORDES_PROFUNDIDAD, "km")

    @router.get("/comparacion-historica")
    async def comparacion_historica(peticion: Request) -> JSONResponse:
        _, pedidos = _leer(peticion, PARAMS_COMPARACION)
        generado = reloj()
        # Magnitud mínima efectiva = máx(4, pedida); la ventana es fija y siempre de eventos reales.
        minima = max(MAGNITUD_MINIMA_COMPARACION, pedidos.magnitud_min or 0.0)
        efectivos = replace(pedidos, magnitud_min=minima, incluir_sinteticos=False)
        reciente = replace(efectivos, desde=generado - timedelta(hours=24), hasta=generado)

        donde, params = construir_where(reciente)
        n_24h = (await ejecutar(db, sql.con_where(sql.SQL_TOTAL, donde), params))[0][0]

        cargado, n_2025 = False, None
        if (await ejecutar(db, sql.SQL_HISTORICO_EXISTE))[0][0]:
            cargado = (await ejecutar(db, sql.SQL_HISTORICO_CARGADO))[0][0]
        if cargado:
            donde, params = construir_where(efectivos, fechas=False, sinteticos=False)
            n_2025 = (await ejecutar(db, sql.con_where(sql.SQL_HISTORICO_RECUENTO, donde), params))[0][0]
        historico, cociente = comparar(n_24h, n_2025, cargado)
        return JSONResponse(
            {
                "ventana_actual": {"desde": iso_utc(reciente.desde), "hasta": iso_utc(reciente.hasta), "eventos": n_24h},
                "historico_2025": historico,
                "cociente": cociente,
                "filtros_efectivos": {
                    "magnitud_min": efectivos.magnitud_min,
                    "magnitud_max": efectivos.magnitud_max,
                    "pais": efectivos.pais,
                    "subregion": efectivos.subregion,
                },
                "aviso": AVISO_COMPARACION + ("" if cargado else AVISO_NO_CARGADO),
                "generated_at": iso_utc(generado),
            }
        )

    return router
