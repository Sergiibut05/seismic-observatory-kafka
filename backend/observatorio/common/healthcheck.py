"""Healthcheck de Compose: `python -m observatorio.common.healthcheck` (código de salida 0/1).

Consulta `http://127.0.0.1:<HEALTH_PORT>/health` dentro del propio contenedor.
`HEALTH_PORT` es la única variable que lee (defecto 8081); la URL no es configurable.
"""

import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping

PUERTO_POR_DEFECTO = 8081
TIEMPO_ESPERA = 3


def url_salud(env: Mapping[str, str]) -> str:
    bruto = env.get("HEALTH_PORT") or str(PUERTO_POR_DEFECTO)
    puerto = int(bruto)
    if not 1 <= puerto <= 65535:
        raise ValueError("HEALTH_PORT fuera de rango")
    return f"http://127.0.0.1:{puerto}/health"


def main(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    try:
        url = url_salud(env)
        # Sin proxies: la consulta es siempre local al contenedor.
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with abridor.open(url, timeout=TIEMPO_ESPERA) as respuesta:
            return 0 if respuesta.status == 200 else 1
    except (ValueError, urllib.error.URLError, OSError):
        # HTTPError (503) es subclase de URLError; cualquier fallo de conexión cuenta como no sano.
        return 1


if __name__ == "__main__":
    sys.exit(main())
