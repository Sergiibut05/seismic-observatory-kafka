"""Pruebas del estado de salud, del servidor /health y del CLI healthcheck."""

import asyncio
import json
import threading

import pytest

from observatorio.common import healthcheck
from observatorio.common.health import EstadoSalud, servidor_salud


# --- EstadoSalud ----------------------------------------------------------


def test_todas_las_comprobaciones_empiezan_en_rojo():
    estado = EstadoSalud(["kafka", "postgres", "catalogo"])
    assert not estado.sano
    assert estado.fallando() == ["kafka", "postgres", "catalogo"]


def test_sano_solo_con_todas_en_verde():
    estado = EstadoSalud(["kafka", "postgres"])
    estado.marcar("kafka", True)
    assert not estado.sano
    assert estado.fallando() == ["postgres"]
    estado.marcar("postgres", True)
    assert estado.sano
    assert estado.fallando() == []


def test_al_poner_una_en_rojo_vuelve_a_no_sano_y_failing_la_nombra():
    estado = EstadoSalud(["kafka", "postgres"])
    estado.marcar("kafka", True)
    estado.marcar("postgres", True)
    estado.marcar("postgres", False)
    assert not estado.sano
    assert estado.fallando() == ["postgres"]


def test_marcar_una_comprobacion_desconocida_es_un_error():
    estado = EstadoSalud(["kafka"])
    with pytest.raises(KeyError):
        estado.marcar("otra", True)


def test_sin_comprobaciones_no_es_sano():
    # Un servicio sin nada registrado no puede declararse sano por omisión.
    assert not EstadoSalud([]).sano


# --- servidor HTTP --------------------------------------------------------


async def peticion(puerto, linea="GET /health HTTP/1.1"):
    lector, escritor = await asyncio.open_connection("127.0.0.1", puerto)
    escritor.write(f"{linea}\r\nHost: x\r\n\r\n".encode())
    await escritor.drain()
    datos = await lector.read()
    escritor.close()
    cabecera, _, cuerpo = datos.partition(b"\r\n\r\n")
    codigo = int(cabecera.split(b" ", 2)[1])
    return codigo, cuerpo.decode(), cabecera.decode()


async def con_servidor(estado, accion):
    servidor = await servidor_salud(estado, 0, host="127.0.0.1")
    puerto = servidor.sockets[0].getsockname()[1]
    try:
        return await accion(puerto)
    finally:
        servidor.close()
        await servidor.wait_closed()


def test_health_503_con_lista_de_fallos():
    estado = EstadoSalud(["kafka", "postgres"])
    estado.marcar("kafka", True)

    async def accion(puerto):
        return await peticion(puerto)

    codigo, cuerpo, cabecera = asyncio.run(con_servidor(estado, accion))
    assert codigo == 503
    assert json.loads(cuerpo) == {"status": "unhealthy", "failing": ["postgres"]}
    assert "application/json" in cabecera


def test_health_200_cuando_todo_esta_en_verde():
    estado = EstadoSalud(["kafka"])
    estado.marcar("kafka", True)

    async def accion(puerto):
        return await peticion(puerto)

    codigo, cuerpo, _ = asyncio.run(con_servidor(estado, accion))
    assert codigo == 200
    assert json.loads(cuerpo) == {"status": "ok"}


def test_el_servidor_refleja_los_cambios_de_estado():
    estado = EstadoSalud(["kafka"])

    async def accion(puerto):
        antes = await peticion(puerto)
        estado.marcar("kafka", True)
        durante = await peticion(puerto)
        estado.marcar("kafka", False)
        despues = await peticion(puerto)
        return antes[0], durante[0], despues[0]

    assert asyncio.run(con_servidor(estado, accion)) == (503, 200, 503)


def test_ruta_desconocida_404():
    estado = EstadoSalud(["kafka"])

    async def accion(puerto):
        return await peticion(puerto, "GET /otra HTTP/1.1")

    codigo, _, _ = asyncio.run(con_servidor(estado, accion))
    assert codigo == 404


def test_metodo_no_permitido_405():
    estado = EstadoSalud(["kafka"])

    async def accion(puerto):
        return await peticion(puerto, "POST /health HTTP/1.1")

    codigo, _, _ = asyncio.run(con_servidor(estado, accion))
    assert codigo == 405


def test_peticion_malformada_no_rompe_el_servidor():
    estado = EstadoSalud(["kafka"])
    estado.marcar("kafka", True)

    async def accion(puerto):
        lector, escritor = await asyncio.open_connection("127.0.0.1", puerto)
        escritor.write(b"\x00\x01basura\r\n\r\n")
        await escritor.drain()
        await lector.read()
        escritor.close()
        return await peticion(puerto)

    codigo, _, _ = asyncio.run(con_servidor(estado, accion))
    assert codigo == 200


# --- CLI healthcheck ------------------------------------------------------


def test_url_por_defecto_usa_el_puerto_8081():
    assert healthcheck.url_salud({}) == "http://127.0.0.1:8081/health"


def test_url_usa_solo_health_port():
    entorno = {"HEALTH_PORT": "8000", "HEALTH_URL": "http://otro:1/x"}
    assert healthcheck.url_salud(entorno) == "http://127.0.0.1:8000/health"


def test_url_con_puerto_invalido_es_un_error():
    with pytest.raises(ValueError):
        healthcheck.url_salud({"HEALTH_PORT": "abc"})


class ServidorEnHilo:
    """Servidor de salud real en otro hilo, para ejecutar el CLI síncrono contra él."""

    def __init__(self, estado):
        self.estado = estado
        self.puerto = None
        self._listo = threading.Event()
        self._hilo = threading.Thread(target=self._ejecutar, daemon=True)

    def _ejecutar(self):
        async def principal():
            servidor = await servidor_salud(self.estado, 0, host="127.0.0.1")
            self.puerto = servidor.sockets[0].getsockname()[1]
            self.parar = asyncio.Event()
            self._bucle = asyncio.get_running_loop()
            self._listo.set()
            await self.parar.wait()
            servidor.close()
            await servidor.wait_closed()

        asyncio.run(principal())

    def __enter__(self):
        self._hilo.start()
        assert self._listo.wait(5)
        return self

    def __exit__(self, *args):
        self._bucle.call_soon_threadsafe(self.parar.set)
        self._hilo.join(5)


def test_cli_devuelve_0_con_200():
    estado = EstadoSalud(["kafka"])
    estado.marcar("kafka", True)
    with ServidorEnHilo(estado) as srv:
        assert healthcheck.main({"HEALTH_PORT": str(srv.puerto)}) == 0


def test_cli_devuelve_1_con_503():
    estado = EstadoSalud(["kafka"])
    with ServidorEnHilo(estado) as srv:
        assert healthcheck.main({"HEALTH_PORT": str(srv.puerto)}) == 1


def test_cli_devuelve_1_con_conexion_rechazada():
    # Puerto 1: nadie escucha.
    assert healthcheck.main({"HEALTH_PORT": "1"}) == 1


def test_cli_devuelve_1_con_puerto_invalido():
    assert healthcheck.main({"HEALTH_PORT": "abc"}) == 1
