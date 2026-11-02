"""Supervisor de una sesión con una dependencia (Kafka o PostgreSQL): sonda periódica y recreación (R-13).

Mantiene una sesión abierta, la sondea cada `HEALTH_PROBE_INTERVAL_SECONDS` y refleja el resultado
en la comprobación de salud. Tras `PROBE_FALLOS_REINICIO` fallos **consecutivos** cierra la sesión y
abre otra con backoff. Nunca termina el proceso: un contenedor no debe reiniciarse por una
dependencia caída (el reinicio no arregla la dependencia y sí pierde estado).
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from observatorio.common.health import EstadoSalud
from observatorio.common.logging import registrar
from observatorio.common.retry import motivo_de, reintentar

_log = logging.getLogger("observatorio.supervisor")


async def _cerrar_sesion(sesion: Any, cerrar: Callable[[Any], Awaitable[None]] | None) -> None:
    if cerrar is None:
        return
    # Un fallo al cerrar una sesión ya rota no debe impedir abrir la siguiente.
    with contextlib.suppress(Exception):
        await cerrar(sesion)


async def supervisar(
    abrir_sesion: Callable[[], Awaitable[Any]],
    sonda: Callable[[Any], Awaitable[bool | None]],
    comprobacion: str,
    estado: EstadoSalud,
    config: Any,
    *,
    cerrar: Callable[[Any], Awaitable[None]] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    logger: logging.Logger = _log,
    registrar_listo: bool = True,
) -> None:
    """Bucle infinito; solo termina por cancelación (`asyncio.CancelledError` se propaga).

    - `abrir_sesion`: crea y devuelve la sesión; si lanza, se reintenta con backoff (`result=reintento`).
    - `sonda(sesion)`: éxito si no lanza y no devuelve `False`.
    - `config`: necesita `backoff`, `health_probe_interval_seconds` y `probe_fallos_reinicio`.
    - `registrar_listo=False`: la apertura ya escribe su propio `result=listo` (p. ej. `Database.conectar`).
    """
    while True:
        estado.marcar(comprobacion, False)
        sesion = await reintentar(
            abrir_sesion,
            dependency=comprobacion,
            config=config.backoff,
            sleep=sleep,
            logger=logger,
        )
        estado.marcar(comprobacion, True)
        if registrar_listo:
            registrar(logger, "listo", component=comprobacion)
        fallos = 0
        sano = True
        try:
            while fallos < config.probe_fallos_reinicio:
                await sleep(config.health_probe_interval_seconds)
                motivo = None
                try:
                    resultado = await sonda(sesion)
                except Exception as exc:
                    resultado, motivo = False, motivo_de(exc)
                if resultado is not False:
                    if not sano and registrar_listo:
                        registrar(logger, "listo", component=comprobacion)
                    fallos, sano = 0, True
                    estado.marcar(comprobacion, True)
                    continue
                fallos += 1
                if sano:
                    # Un solo aviso por caída; los siguientes fallos no repiten la línea.
                    registrar(
                        logger,
                        "error",
                        nivel="WARNING",
                        component=comprobacion,
                        reason=motivo or "sonda_fallida",
                    )
                sano = False
                estado.marcar(comprobacion, False)
        finally:
            await _cerrar_sesion(sesion, cerrar)
        registrar(
            logger,
            "info",
            component=comprobacion,
            action="sesion_recreada",
            fallos=fallos,
        )
