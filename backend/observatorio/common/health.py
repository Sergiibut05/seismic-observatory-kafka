"""Estado de salud por comprobaciones y servidor HTTP mínimo con `GET /health` (R-12)."""

import asyncio
import json
import logging
from collections.abc import Iterable

_log = logging.getLogger("observatorio.health")

_TIEMPO_LECTURA = 5.0
_MOTIVOS = {200: "OK", 404: "Not Found", 405: "Method Not Allowed", 503: "Service Unavailable"}


class EstadoSalud:
    """Registro de comprobaciones. Todas empiezan en rojo: «sano» exige conexiones establecidas."""

    def __init__(self, nombres: Iterable[str]):
        self._comprobaciones = {nombre: False for nombre in nombres}

    def marcar(self, nombre: str, ok: bool) -> None:
        if nombre not in self._comprobaciones:
            raise KeyError(nombre)
        self._comprobaciones[nombre] = bool(ok)

    def fallando(self) -> list[str]:
        return [nombre for nombre, ok in self._comprobaciones.items() if not ok]

    @property
    def sano(self) -> bool:
        return bool(self._comprobaciones) and not self.fallando()


def cuerpo_salud(estado: EstadoSalud) -> tuple[int, dict]:
    if estado.sano:
        return 200, {"status": "ok"}
    return 503, {"status": "unhealthy", "failing": estado.fallando()}


def _respuesta(codigo: int, cuerpo: dict) -> bytes:
    datos = json.dumps(cuerpo, separators=(",", ":")).encode()
    cabecera = (
        f"HTTP/1.1 {codigo} {_MOTIVOS[codigo]}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(datos)}\r\n"
        "Connection: close\r\n\r\n"
    )
    return cabecera.encode() + datos


async def servidor_salud(estado: EstadoSalud, puerto: int, host: str = "0.0.0.0") -> asyncio.Server:
    """Arranca el servidor de salud en el mismo bucle de eventos que el servicio."""

    async def atender(lector: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        try:
            linea = await asyncio.wait_for(lector.readline(), _TIEMPO_LECTURA)
            # Se descartan las cabeceras hasta la línea en blanco.
            while True:
                cabecera = await asyncio.wait_for(lector.readline(), _TIEMPO_LECTURA)
                if cabecera in (b"\r\n", b"\n", b""):
                    break
            partes = linea.decode("latin-1").split()
            if len(partes) < 2:
                codigo, cuerpo = 404, {"status": "not_found"}
            elif partes[1].split("?")[0] != "/health":
                codigo, cuerpo = 404, {"status": "not_found"}
            elif partes[0] != "GET":
                codigo, cuerpo = 405, {"status": "method_not_allowed"}
            else:
                codigo, cuerpo = cuerpo_salud(estado)
            escritor.write(_respuesta(codigo, cuerpo))
            await escritor.drain()
        except (asyncio.TimeoutError, ConnectionError, asyncio.IncompleteReadError, ValueError):
            pass
        finally:
            escritor.close()

    return await asyncio.start_server(atender, host, puerto)
