"""Pruebas del procesamiento de un registro y del orden transacción → log → commit del offset."""

import asyncio
import io
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from aiokafka import TopicPartition

from observatorio.common.logging import FormateadorClaveValor
from observatorio.common.retry import Backoff
from observatorio.consumer import app as consumidor_app

EJEMPLO = Path(__file__).resolve().parent.parent / "fixtures" / "mensaje_v1_ejemplo.json"
BACKOFF = Backoff(1, 2, 30)


@pytest.fixture
def salida():
    return io.StringIO()


@pytest.fixture
def logger(salida):
    log = logging.getLogger(f"prueba.bucle.{id(salida)}")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorClaveValor("consumer"))
    log.addHandler(manejador)
    return log


def registro(valor=None, clave=b"synthetic-smoke-0001", offset=5):
    return SimpleNamespace(
        key=clave,
        value=EJEMPLO.read_bytes() if valor is None else valor,
        topic="eventos.live",
        partition=2,
        offset=offset,
    )


class BdFalsa:
    def __init__(self, conectada=True):
        self.conectada = conectada
        self.reconexiones = 0

    async def conectar(self):
        self.reconexiones += 1
        self.conectada = True


@pytest.fixture
def escrituras(monkeypatch):
    """Sustituye la persistencia y anota las llamadas en orden."""
    estado = SimpleNamespace(llamadas=[], versiones=[1], cuarentenas=[], fallos=[])

    async def guardar_version(db, version, reg, esquema):
        estado.llamadas.append("guardar_version")
        if estado.fallos:
            raise estado.fallos.pop(0)
        return estado.versiones.pop(0) if len(estado.versiones) > 1 else estado.versiones[0]

    async def guardar_cuarentena(db, motivo, detalle, reg):
        estado.llamadas.append("guardar_cuarentena")
        estado.cuarentenas.append((motivo, detalle, reg.offset))
        return 1

    monkeypatch.setattr(consumidor_app, "guardar_version", guardar_version)
    monkeypatch.setattr(consumidor_app, "guardar_cuarentena", guardar_cuarentena)
    return estado


# --- procesar_registro ----------------------------------------------------


def test_version_nueva_es_persistida(escrituras, logger, salida):
    resultado = asyncio.run(consumidor_app.procesar_registro(BdFalsa(), registro(), logger))
    assert resultado == "persistido"
    linea = salida.getvalue().strip()
    assert "result=persistido event_id=synthetic-smoke-0001 updated=1767225600000 topic=eventos.live partition=2 offset=5" in linea


def test_version_repetida_es_omitida_como_duplicado(escrituras, logger, salida):
    escrituras.versiones = [0]
    resultado = asyncio.run(consumidor_app.procesar_registro(BdFalsa(), registro(), logger))
    assert resultado == "omitido"
    linea = salida.getvalue().strip()
    assert "result=omitido event_id=synthetic-smoke-0001 updated=1767225600000 reason=duplicado" in linea


def test_registro_invalido_va_a_cuarentena_sin_event_id(escrituras, logger, salida):
    resultado = asyncio.run(consumidor_app.procesar_registro(BdFalsa(), registro(valor=b"{roto", clave=b"k"), logger))
    assert resultado == "rechazado"
    assert escrituras.llamadas == ["guardar_cuarentena"]
    assert escrituras.cuarentenas[0][0] == "json_ilegible"
    linea = salida.getvalue().strip()
    assert "level=WARNING" in linea
    assert "result=rechazado event_id=- updated=- motivo=json_ilegible" in linea


def test_rechazo_con_evento_conocido_lo_registra(escrituras, logger, salida):
    asyncio.run(consumidor_app.procesar_registro(BdFalsa(), registro(clave=b"otra"), logger))
    assert "event_id=synthetic-smoke-0001 updated=1767225600000 motivo=clave_distinta_de_id" in salida.getvalue()


def test_error_de_dato_se_guarda_como_no_almacenable(escrituras, logger, salida):
    escrituras.fallos = [psycopg.errors.UntranslatableCharacter("\\u0000")]
    resultado = asyncio.run(consumidor_app.procesar_registro(BdFalsa(), registro(), logger))
    assert resultado == "rechazado"
    assert escrituras.llamadas == ["guardar_version", "guardar_cuarentena"]
    assert escrituras.cuarentenas == [("no_almacenable", "sqlstate=22P05", 5)]
    assert "motivo=no_almacenable" in salida.getvalue()
    assert "result=persistido" not in salida.getvalue()


def test_error_de_conexion_se_propaga_para_reintentar(escrituras, logger):
    escrituras.fallos = [psycopg.OperationalError("caído")]
    with pytest.raises(psycopg.OperationalError):
        asyncio.run(consumidor_app.procesar_registro(BdFalsa(), registro(), logger))
    assert escrituras.cuarentenas == []


# --- procesar_con_reintentos ----------------------------------------------


class Reloj:
    def __init__(self):
        self.esperas = []

    async def sleep(self, s):
        self.esperas.append(s)


def test_error_de_conexion_reintenta_el_mismo_registro_y_reconecta(escrituras, logger, salida):
    escrituras.fallos = [psycopg.OperationalError("a"), psycopg.OperationalError("b")]
    db = BdFalsa(conectada=False)
    reloj = Reloj()
    resultado = asyncio.run(consumidor_app.procesar_con_reintentos(db, registro(), BACKOFF, reloj.sleep, logger))
    assert resultado == "persistido"
    assert escrituras.llamadas == ["guardar_version"] * 3
    assert reloj.esperas == [1, 2]
    assert db.reconexiones == 1
    texto = salida.getvalue()
    assert texto.count("result=reintento") == 2
    assert "dependency=postgres" in texto
    assert "reason=OperationalError" in texto
    assert "result=persistido" in texto


def test_sin_conexion_no_llega_a_cuarentena(escrituras, logger):
    from observatorio.common.db import SinConexion

    escrituras.fallos = [SinConexion("x")]
    reloj = Reloj()
    asyncio.run(consumidor_app.procesar_con_reintentos(BdFalsa(), registro(), BACKOFF, reloj.sleep, logger))
    assert escrituras.cuarentenas == []
    assert reloj.esperas == [1]


def test_error_desconocido_se_registra_con_traza_y_se_reintenta(escrituras, logger, salida):
    escrituras.fallos = [RuntimeError("inesperado")]
    reloj = Reloj()
    resultado = asyncio.run(consumidor_app.procesar_con_reintentos(BdFalsa(), registro(), BACKOFF, reloj.sleep, logger))
    assert resultado == "persistido"
    assert reloj.esperas == [1]
    lineas = [l for l in salida.getvalue().split("\n") if l]
    assert "result=error" in lineas[0]
    assert "reason=RuntimeError" in lineas[0]
    assert "exc=" in lineas[0] and "inesperado" in lineas[0]
    assert len(lineas) == 2


def test_el_registro_invalido_no_se_reintenta(escrituras, logger):
    reloj = Reloj()
    asyncio.run(consumidor_app.procesar_con_reintentos(BdFalsa(), registro(valor=b"{roto"), BACKOFF, reloj.sleep, logger))
    assert reloj.esperas == []
    assert len(escrituras.cuarentenas) == 1


# --- confirmar_offset -----------------------------------------------------


class ConsumidorFalso:
    def __init__(self, registros=(), parada=None, falla_commit=None, eventos=None):
        self._registros = list(registros)
        self._parada = parada
        self.commits = []
        self._falla = falla_commit
        self._eventos = eventos if eventos is not None else []

    async def getone(self):
        reg = self._registros.pop(0)
        if not self._registros and self._parada is not None:
            self._parada.set()
        return reg

    async def commit(self, offsets):
        self._eventos.append("commit")
        if self._falla:
            raise self._falla
        self.commits.append(offsets)


def test_se_confirma_el_offset_siguiente(logger):
    consumidor = ConsumidorFalso()
    asyncio.run(consumidor_app.confirmar_offset(consumidor, registro(offset=7), logger))
    assert consumidor.commits == [{TopicPartition("eventos.live", 2): 8}]


def test_fallo_del_commit_se_registra_como_error(logger, salida):
    consumidor = ConsumidorFalso(falla_commit=RuntimeError("reasignado"))
    ok = asyncio.run(consumidor_app.confirmar_offset(consumidor, registro(), logger))
    assert ok is False
    assert "result=error" in salida.getvalue()
    assert "action=commit_offset" in salida.getvalue()


def test_el_commit_del_offset_es_posterior_a_la_escritura(escrituras, monkeypatch):
    """Constitución III: ningún commit de offset antes del commit de PostgreSQL."""
    eventos = escrituras.llamadas
    parada = asyncio.Event()

    async def principal():
        consumidor = ConsumidorFalso([registro(offset=0), registro(valor=b"{roto", clave=b"k", offset=1)], parada, eventos=eventos)
        ajustes = SimpleNamespace(backoff=BACKOFF)
        await consumidor_app._consumir(ajustes, consumidor, BdFalsa(), parada)
        return consumidor

    consumidor = asyncio.run(principal())
    assert eventos == ["guardar_version", "commit", "guardar_cuarentena", "commit"]
    assert [list(c.values())[0] for c in consumidor.commits] == [1, 2]
