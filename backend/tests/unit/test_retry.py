"""Pruebas del backoff y de los reintentos (R-13)."""

import asyncio
import io
import itertools
import logging
import re

import pytest

from observatorio.common.logging import FormateadorClaveValor
from observatorio.common.retry import Backoff, FalloDependencia, esperas, reintentar


def primeras(n, **kw):
    return list(itertools.islice(esperas(**kw), n))


def test_esperas_por_defecto():
    assert primeras(9, inicial=1, factor=2, tope=30) == [1, 2, 4, 8, 16, 30, 30, 30, 30]


def test_esperas_con_otra_configuracion():
    assert primeras(6, inicial=2, factor=3, tope=20) == [2, 6, 18, 20, 20, 20]


def test_esperas_con_inicial_mayor_que_tope_se_acota():
    assert primeras(3, inicial=5, factor=2, tope=5) == [5, 5, 5]


@pytest.fixture
def salida():
    return io.StringIO()


@pytest.fixture
def logger(salida):
    log = logging.getLogger(f"prueba.retry.{id(salida)}")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorClaveValor("consumer"))
    log.addHandler(manejador)
    return log


class Reloj:
    """`sleep` falso: anota las esperas pedidas sin esperar."""

    def __init__(self):
        self.esperas = []

    async def sleep(self, segundos):
        self.esperas.append(segundos)


def operacion_que_falla(veces, excepcion=ConnectionRefusedError):
    estado = {"llamadas": 0}

    async def operacion():
        estado["llamadas"] += 1
        if estado["llamadas"] <= veces:
            raise excepcion("secreto-que-no-debe-salir")
        return "listo"

    return operacion, estado


def lineas(salida):
    return [l for l in salida.getvalue().split("\n") if l]


def test_reintenta_hasta_el_exito_y_devuelve_el_resultado(logger, salida):
    reloj = Reloj()
    operacion, estado = operacion_que_falla(3)
    resultado = asyncio.run(
        reintentar(operacion, dependency="postgres", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger)
    )
    assert resultado == "listo"
    assert estado["llamadas"] == 4
    assert reloj.esperas == [1, 2, 4]


def test_registra_cada_intento_con_sus_campos(logger, salida):
    reloj = Reloj()
    operacion, _ = operacion_que_falla(3)
    asyncio.run(reintentar(operacion, dependency="kafka", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger))
    ls = lineas(salida)
    assert len(ls) == 3
    for numero, (linea, espera) in enumerate(zip(ls, [1, 2, 4]), start=1):
        assert "result=reintento" in linea
        assert f"attempt={numero}" in linea
        assert f"wait_s={espera}" in linea
        assert "dependency=kafka" in linea
        assert "reason=ConnectionRefusedError" in linea


def test_reason_nunca_incluye_el_mensaje_de_la_excepcion(logger, salida):
    reloj = Reloj()
    operacion, _ = operacion_que_falla(1)
    asyncio.run(reintentar(operacion, dependency="kafka", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger))
    assert "secreto-que-no-debe-salir" not in salida.getvalue()


def test_reason_de_un_fallo_de_dependencia_es_su_codigo(logger, salida):
    reloj = Reloj()

    async def operacion():
        if not reloj.esperas:
            raise FalloDependencia("esquema_desactualizado")

    asyncio.run(
        reintentar(operacion, dependency="postgres", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger)
    )
    assert "reason=esquema_desactualizado" in salida.getvalue()


def test_las_esperas_se_acotan_al_tope(logger, salida):
    reloj = Reloj()
    operacion, _ = operacion_que_falla(8)
    asyncio.run(reintentar(operacion, dependency="kafka", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger))
    assert reloj.esperas == [1, 2, 4, 8, 16, 30, 30, 30]


def test_no_termina_el_proceso_ante_excepciones_esperadas(logger):
    reloj = Reloj()
    for excepcion in (ConnectionRefusedError, TimeoutError, OSError, RuntimeError):
        operacion, _ = operacion_que_falla(2, excepcion)
        asyncio.run(
            reintentar(operacion, dependency="x", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger)
        )


def test_propaga_cancelled_error(logger):
    reloj = Reloj()

    async def operacion():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(reintentar(operacion, dependency="x", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger))
    assert reloj.esperas == []


def test_cancelacion_durante_la_espera_se_propaga(logger):
    async def sleep(_):
        raise asyncio.CancelledError()

    operacion, _ = operacion_que_falla(5)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(reintentar(operacion, dependency="x", config=Backoff(1, 2, 30), sleep=sleep, logger=logger))


def test_la_secuencia_de_esperas_se_reinicia_tras_un_exito(logger, salida):
    reloj = Reloj()
    for _ in range(2):
        operacion, _ = operacion_que_falla(2)
        asyncio.run(
            reintentar(operacion, dependency="kafka", config=Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger)
        )
    assert reloj.esperas == [1, 2, 1, 2]
    intentos = re.findall(r"attempt=(\d+)", salida.getvalue())
    assert intentos == ["1", "2", "1", "2"]


def test_solo_reintenta_las_excepciones_indicadas(logger):
    reloj = Reloj()

    async def operacion():
        raise KeyError("no esperada")

    with pytest.raises(KeyError):
        asyncio.run(
            reintentar(
                operacion,
                dependency="x",
                config=Backoff(1, 2, 30),
                sleep=reloj.sleep,
                logger=logger,
                excepciones=(ConnectionError,),
            )
        )
    assert reloj.esperas == []
