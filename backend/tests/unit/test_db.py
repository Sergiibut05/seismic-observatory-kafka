"""Pruebas de la conexión a PostgreSQL con una fábrica falsa inyectada (R-01, R-07, R-13)."""

import asyncio
import io
import logging

import psycopg
import pytest

from observatorio.common.config import AjustesPostgres
from observatorio.common.db import (
    ESQUEMA_VERSION_REQUERIDA,
    Database,
    SinConexion,
    parametros_conexion,
)
from observatorio.common.health import EstadoSalud
from observatorio.common.logging import FormateadorClaveValor
from observatorio.common.retry import Backoff

CONTRASENA = "clave-ultra-secreta"


class CursorFalso:
    def __init__(self, filas):
        self._filas = filas

    async def fetchone(self):
        return self._filas[0] if self._filas else None

    async def fetchall(self):
        return list(self._filas)


class ConexionFalsa:
    def __init__(self, version=1, tabla_existe=True, falla_sonda=False, consulta_cuelga=False):
        self.version = version
        self.tabla_existe = tabla_existe
        self.falla_sonda = falla_sonda
        self.consulta_cuelga = consulta_cuelga
        self.cerrada = False
        self.consultas = []

    async def execute(self, sql, params=None):
        self.consultas.append(sql)
        if self.consulta_cuelga:
            await asyncio.sleep(10)
        if "version_esquema" in sql:
            if not self.tabla_existe:
                raise psycopg.errors.UndefinedTable("no existe la tabla")
            return CursorFalso([(self.version,)])
        if sql.strip().upper().startswith("SELECT 1"):
            if self.falla_sonda:
                raise psycopg.OperationalError(f"conexión perdida con password={CONTRASENA}")
            return CursorFalso([(1,)])
        return CursorFalso([("fila", 1)])

    async def close(self):
        self.cerrada = True


class Reloj:
    def __init__(self):
        self.esperas = []

    async def sleep(self, s):
        self.esperas.append(s)


@pytest.fixture
def salida():
    return io.StringIO()


@pytest.fixture
def logger(salida):
    log = logging.getLogger(f"prueba.db.{id(salida)}")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorClaveValor("consumer", secretos=[CONTRASENA]))
    log.addHandler(manejador)
    return log


def fabrica_con(*resultados):
    """Fábrica falsa: cada llamada consume un resultado (excepción o conexión)."""
    pendientes = list(resultados)
    llamadas = []

    async def fabrica():
        llamadas.append(1)
        resultado = pendientes.pop(0) if len(pendientes) > 1 else pendientes[0]
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado

    fabrica.llamadas = llamadas
    return fabrica


def crear(fabrica, logger, estado=None, reloj=None):
    reloj = reloj or Reloj()
    return Database(
        fabrica,
        Backoff(1, 2, 30),
        estado=estado,
        sleep=reloj.sleep,
        logger=logger,
    ), reloj


# --- conexión y backoff ---------------------------------------------------


def test_constante_de_version_requerida():
    assert ESQUEMA_VERSION_REQUERIDA == 1


def test_conecta_al_primer_intento(logger, salida):
    conexion = ConexionFalsa()
    db, reloj = crear(fabrica_con(conexion), logger)
    asyncio.run(db.conectar())
    assert db.conectada
    assert reloj.esperas == []
    assert "result=reintento" not in salida.getvalue()


def test_con_fallos_reintenta_con_backoff_y_registra_postgres(logger, salida):
    conexion = ConexionFalsa()
    fabrica = fabrica_con(ConnectionRefusedError("no"), psycopg.OperationalError("caído"), conexion)
    db, reloj = crear(fabrica, logger)
    asyncio.run(db.conectar())
    assert db.conectada
    assert reloj.esperas == [1, 2]
    texto = salida.getvalue()
    assert texto.count("result=reintento") == 2
    assert "dependency=postgres" in texto
    assert "attempt=1" in texto and "attempt=2" in texto


def test_marca_la_comprobacion_postgres_en_verde_al_conectar(logger):
    estado = EstadoSalud(["postgres"])
    db, _ = crear(fabrica_con(ConexionFalsa()), logger, estado=estado)
    assert not estado.sano
    asyncio.run(db.conectar())
    assert estado.sano


# --- guarda de versión de esquema -----------------------------------------


def test_esquema_desactualizado_se_trata_como_fallo_y_se_reintenta(logger, salida):
    vieja = ConexionFalsa(version=0)
    buena = ConexionFalsa(version=1)
    db, reloj = crear(fabrica_con(vieja, buena), logger)
    asyncio.run(db.conectar())
    assert db.conectada
    assert vieja.cerrada
    assert reloj.esperas == [1]
    assert "reason=esquema_desactualizado" in salida.getvalue()


def test_tabla_inexistente_tambien_es_esquema_desactualizado(logger, salida):
    sin_tabla = ConexionFalsa(tabla_existe=False)
    buena = ConexionFalsa()
    db, reloj = crear(fabrica_con(sin_tabla, buena), logger)
    asyncio.run(db.conectar())
    assert sin_tabla.cerrada
    assert "reason=esquema_desactualizado" in salida.getvalue()
    assert db.conectada


def test_version_mayor_a_la_requerida_es_valida(logger):
    db, reloj = crear(fabrica_con(ConexionFalsa(version=7)), logger)
    asyncio.run(db.conectar())
    assert reloj.esperas == []


def test_tabla_vacia_sin_version_es_desactualizada(logger, salida):
    class SinFilas(ConexionFalsa):
        async def execute(self, sql, params=None):
            if "version_esquema" in sql:
                return CursorFalso([(None,)])
            return await super().execute(sql, params)

    db, reloj = crear(fabrica_con(SinFilas(), ConexionFalsa()), logger)
    asyncio.run(db.conectar())
    assert reloj.esperas == [1]
    assert "reason=esquema_desactualizado" in salida.getvalue()


# --- sonda ----------------------------------------------------------------


def test_sonda_correcta_mantiene_la_conexion(logger):
    estado = EstadoSalud(["postgres"])
    db, _ = crear(fabrica_con(ConexionFalsa()), logger, estado=estado)

    async def escenario():
        await db.conectar()
        return await db.sonda()

    assert asyncio.run(escenario()) is True
    assert db.conectada
    assert estado.sano


def test_sonda_que_falla_marca_desconectado_y_pone_la_comprobacion_en_rojo(logger):
    estado = EstadoSalud(["postgres"])
    conexion = ConexionFalsa(falla_sonda=True)
    db, _ = crear(fabrica_con(conexion), logger, estado=estado)

    async def escenario():
        await db.conectar()
        assert estado.sano
        return await db.sonda()

    assert asyncio.run(escenario()) is False
    assert not db.conectada
    assert not estado.sano
    assert estado.fallando() == ["postgres"]
    assert conexion.cerrada


def test_sonda_sin_conexion_devuelve_false(logger):
    db, _ = crear(fabrica_con(ConexionFalsa()), logger)
    assert asyncio.run(db.sonda()) is False


def test_sonda_que_se_cuelga_agota_el_tiempo(logger):
    conexion = ConexionFalsa()
    db, _ = crear(fabrica_con(conexion), logger)
    db.timeout_sonda = 0.05

    async def escenario():
        await db.conectar()
        conexion.consulta_cuelga = True
        return await db.sonda()

    assert asyncio.run(escenario()) is False
    assert not db.conectada


# --- consultas ------------------------------------------------------------


def test_consultar_devuelve_filas(logger):
    db, _ = crear(fabrica_con(ConexionFalsa()), logger)

    async def escenario():
        await db.conectar()
        return await db.consultar("SELECT algo FROM tabla")

    assert asyncio.run(escenario()) == [("fila", 1)]


def test_consultar_sin_conexion_lanza_sin_conexion(logger):
    db, _ = crear(fabrica_con(ConexionFalsa()), logger)
    with pytest.raises(SinConexion):
        asyncio.run(db.consultar("SELECT 1"))


def test_consultar_con_fallo_marca_la_conexion_perdida(logger):
    class Falla(ConexionFalsa):
        async def execute(self, sql, params=None):
            if "version_esquema" in sql:
                return await super().execute(sql, params)
            raise psycopg.OperationalError("se cayó")

    estado = EstadoSalud(["postgres"])
    db, _ = crear(fabrica_con(Falla()), logger, estado=estado)

    async def escenario():
        await db.conectar()
        with pytest.raises(psycopg.OperationalError):
            await db.consultar("SELECT algo")

    asyncio.run(escenario())
    assert not db.conectada
    assert not estado.sano


def test_consultar_agota_el_tiempo_y_marca_la_conexion_perdida(logger):
    conexion = ConexionFalsa()
    db, _ = crear(fabrica_con(conexion), logger)

    async def escenario():
        await db.conectar()
        conexion.consulta_cuelga = True
        with pytest.raises(asyncio.TimeoutError):
            await db.consultar("SELECT algo", timeout=0.05)

    asyncio.run(escenario())
    assert not db.conectada


# --- credenciales ---------------------------------------------------------


def test_los_parametros_de_conexion_van_por_separado():
    ajustes = AjustesPostgres(host="postgres", port=5432, user="obs", db="obsdb", password="p@ss w/ord=1")
    parametros = parametros_conexion(ajustes)
    assert parametros["host"] == "postgres"
    assert parametros["port"] == 5432
    assert parametros["user"] == "obs"
    assert parametros["dbname"] == "obsdb"
    assert parametros["password"] == "p@ss w/ord=1"
    assert "conninfo" not in parametros
    assert parametros["autocommit"] is True


def test_la_fabrica_real_no_usa_cadena_de_conexion(monkeypatch):
    capturado = {}

    async def falso_connect(*args, **kwargs):
        capturado["args"] = args
        capturado["kwargs"] = kwargs
        return ConexionFalsa()

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", falso_connect)
    ajustes = AjustesPostgres(host="postgres", port=5432, user="obs", db="obsdb", password="x")
    db = Database.desde_ajustes(ajustes, Backoff(1, 2, 30))
    asyncio.run(db._fabrica())
    assert capturado["args"] == ()
    assert capturado["kwargs"]["password"] == "x"
    assert "conninfo" not in capturado["kwargs"]


def test_ningun_log_contiene_la_contrasena(logger, salida):
    fabrica = fabrica_con(
        psycopg.OperationalError(f"fallo de autenticación password={CONTRASENA}"),
        ConexionFalsa(falla_sonda=True),
    )
    db, _ = crear(fabrica, logger)

    async def escenario():
        await db.conectar()
        await db.sonda()

    asyncio.run(escenario())
    assert CONTRASENA not in salida.getvalue()
    assert "reason=OperationalError" in salida.getvalue()


def test_cerrar_cierra_la_conexion(logger):
    conexion = ConexionFalsa()
    db, _ = crear(fabrica_con(conexion), logger)

    async def escenario():
        await db.conectar()
        await db.cerrar()

    asyncio.run(escenario())
    assert conexion.cerrada
    assert not db.conectada
