"""Parada ordenada: SIGTERM/SIGINT activan un evento.

Python como PID 1 del contenedor ignora SIGTERM si no hay manejador; sin esto,
`docker compose stop` esperaría los 10 s de gracia y terminaría con SIGKILL.
"""

import asyncio
import signal


def evento_de_parada() -> asyncio.Event:
    """Debe llamarse dentro del bucle de eventos en ejecución."""
    parada = asyncio.Event()
    bucle = asyncio.get_running_loop()
    for senal in (signal.SIGTERM, signal.SIGINT):
        try:
            bucle.add_signal_handler(senal, parada.set)
        except NotImplementedError:  # pragma: no cover - solo Windows fuera de contenedor
            signal.signal(senal, lambda *_: bucle.call_soon_threadsafe(parada.set))
    return parada


async def hasta_parada(corrutina, parada: asyncio.Event):
    """Ejecuta `corrutina`; si llega la parada antes, la cancela. Devuelve `(resultado, parado)`."""
    tarea = asyncio.ensure_future(corrutina)
    espera = asyncio.ensure_future(parada.wait())
    try:
        await asyncio.wait({tarea, espera}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        espera.cancel()
    if tarea.done():
        return tarea.result(), False
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass
    return None, True


async def esperar(parada: asyncio.Event, segundos: float) -> bool:
    """Duerme hasta `segundos` o hasta que se pida la parada. Devuelve True si hay que parar."""
    try:
        await asyncio.wait_for(parada.wait(), segundos)
    except asyncio.TimeoutError:
        pass
    return parada.is_set()
