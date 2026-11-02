"""Backoff exponencial y reintentos de conexión con registro de cada intento (R-13)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import TypeVar

from observatorio.common.logging import registrar

T = TypeVar("T")

_log = logging.getLogger("observatorio.retry")


@dataclass(frozen=True)
class Backoff:
    """Parámetros del backoff: espera inicial, factor multiplicador y tope (segundos)."""

    inicial: float
    factor: float
    tope: float


class FalloDependencia(Exception):
    """Fallo de una dependencia con un código de motivo apto para logs (nunca secretos)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def esperas(inicial: float = 1, factor: float = 2, tope: float = 30) -> Iterator[float]:
    """Genera 1, 2, 4, 8, 16, 30, 30… sin desbordar: la espera se acota en cada paso."""
    espera = min(inicial, tope)
    while True:
        yield espera
        espera = min(espera * factor, tope)


def motivo_de(excepcion: BaseException) -> str:
    """Código del motivo: el de `FalloDependencia` o la clase de la excepción, nunca su mensaje."""
    return getattr(excepcion, "reason", None) or type(excepcion).__name__


async def reintentar(
    operacion: Callable[[], Awaitable[T]],
    *,
    dependency: str,
    config: Backoff,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    logger: logging.Logger = _log,
    excepciones: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Ejecuta `operacion` hasta que tenga éxito, con espera creciente entre intentos.

    `asyncio.CancelledError` no es `Exception`, así que siempre se propaga.
    """
    secuencia = esperas(config.inicial, config.factor, config.tope)
    intento = 0
    while True:
        try:
            return await operacion()
        except excepciones as exc:
            intento += 1
            espera = next(secuencia)
            registrar(
                logger,
                "reintento",
                dependency=dependency,
                attempt=intento,
                wait_s=espera,
                reason=motivo_de(exc),
            )
            await sleep(espera)
