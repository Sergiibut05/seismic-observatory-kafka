"""Salud del servicio de fusión: un latido en fichero mientras la consulta de Spark está viva.

Spark no expone un `/health` propio y su interfaz web no se publica. El proceso toca
`FICHERO_LATIDO` cada `INTERVALO_S` mientras la consulta está activa; el healthcheck de Compose
(`python -m observatorio.fusion.salud`) falla si el latido tiene más de `MAXIMO_S`.
"""

import os
import sys
import threading
import time
from pathlib import Path

FICHERO_LATIDO = Path(os.environ.get("FUSION_LATIDO", "/tmp/fusion-latido"))
INTERVALO_S = 10
MAXIMO_S = 60


def latir_mientras(activa, parada: threading.Event, fichero: Path = FICHERO_LATIDO) -> threading.Thread:
    """Hilo que toca el fichero mientras `activa()` sea verdad y no se pida parar."""

    def bucle():
        while not parada.is_set():
            if activa():
                fichero.touch()
            parada.wait(INTERVALO_S)

    hilo = threading.Thread(target=bucle, name="latido-fusion", daemon=True)
    hilo.start()
    return hilo


def sana(fichero: Path = FICHERO_LATIDO, ahora: float | None = None, maximo: float = MAXIMO_S) -> bool:
    try:
        edad = (time.time() if ahora is None else ahora) - fichero.stat().st_mtime
    except FileNotFoundError:
        return False
    return edad <= maximo


if __name__ == "__main__":
    sys.exit(0 if sana() else 1)
