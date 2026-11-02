"""Acceso a PostgreSQL con `psycopg` 3 asíncrono: una conexión, backoff y guarda de esquema (R-01, R-07)."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

import psycopg

from observatorio.common.config import AjustesPostgres
from observatorio.common.health import EstadoSalud
from observatorio.common.logging import registrar
from observatorio.common.retry import Backoff, FalloDependencia, reintentar

_log = logging.getLogger("observatorio.db")

# Versión mínima de `ingesta.version_esquema` que exige el código (R-07).
ESQUEMA_VERSION_REQUERIDA = 1

_CONSULTA_VERSION = "SELECT max(version) FROM ingesta.version_esquema"


class SinConexion(Exception):
    """No hay conexión abierta con PostgreSQL en este momento."""


def parametros_conexion(ajustes: AjustesPostgres) -> dict:
    """Parámetros por separado: sin cadena de conexión, que podría acabar en un log (R-01)."""
    return {
        "host": ajustes.host,
        "port": ajustes.port,
        "user": ajustes.user,
        "password": ajustes.password,
        "dbname": ajustes.db,
        "autocommit": True,
        "connect_timeout": 5,
    }


class Database:
    """Una `AsyncConnection` protegida por un `asyncio.Lock`.

    Con `autocommit=True` las transacciones se abren de forma explícita con
    `async with conn.transaction()`, de modo que se ve dónde empieza y acaba cada commit.
    """

    def __init__(
        self,
        fabrica: Callable[[], Awaitable],
        backoff: Backoff,
        estado: EstadoSalud | None = None,
        comprobacion: str = "postgres",
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        logger: logging.Logger = _log,
        timeout_sonda: float = 3.0,
    ):
        self._fabrica = fabrica
        self._backoff = backoff
        self._estado = estado
        self._comprobacion = comprobacion
        self._sleep = sleep
        self._logger = logger
        self.timeout_sonda = timeout_sonda
        self._conn = None
        self._lock = asyncio.Lock()

    @classmethod
    def desde_ajustes(cls, ajustes: AjustesPostgres, backoff: Backoff, **kwargs) -> "Database":
        async def fabrica():
            return await psycopg.AsyncConnection.connect(**parametros_conexion(ajustes))

        return cls(fabrica, backoff, **kwargs)

    @property
    def conectada(self) -> bool:
        return self._conn is not None

    def _marcar(self, ok: bool) -> None:
        if self._estado is not None:
            self._estado.marcar(self._comprobacion, ok)

    async def _cerrar_conexion(self, conn) -> None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(conn.close(), 2)

    async def _version_esquema(self, conn) -> int | None:
        try:
            cursor = await asyncio.wait_for(conn.execute(_CONSULTA_VERSION), self.timeout_sonda + 2)
            fila = await cursor.fetchone()
        except (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName):
            return None
        return fila[0] if fila else None

    async def _abrir(self) -> None:
        conn = await self._fabrica()
        try:
            version = await self._version_esquema(conn)
        except BaseException:
            await self._cerrar_conexion(conn)
            raise
        if version is None or version < ESQUEMA_VERSION_REQUERIDA:
            await self._cerrar_conexion(conn)
            raise FalloDependencia("esquema_desactualizado")
        self._conn = conn

    async def conectar(self) -> None:
        """Abre la conexión con backoff; vuelve solo cuando está establecida y el esquema es válido."""
        await reintentar(
            self._abrir,
            dependency="postgres",
            config=self._backoff,
            sleep=self._sleep,
            logger=self._logger,
        )
        self._marcar(True)
        registrar(self._logger, "listo", component="postgres")

    async def _perder(self) -> None:
        conn, self._conn = self._conn, None
        self._marcar(False)
        if conn is not None:
            await self._cerrar_conexion(conn)

    async def sonda(self) -> bool:
        """`SELECT 1` con límite de tiempo. Un fallo marca la conexión como perdida."""
        if self._conn is None:
            self._marcar(False)
            return False
        try:
            async with self._lock:
                await asyncio.wait_for(self._conn.execute("SELECT 1"), self.timeout_sonda)
        except Exception:
            await self._perder()
            return False
        self._marcar(True)
        return True

    async def consultar(self, sql: str, params=None, timeout: float = 3.0) -> list[tuple]:
        """Ejecuta una consulta de lectura. Un fallo o un agotamiento de tiempo pierde la conexión."""
        if self._conn is None:
            raise SinConexion("sin conexión con PostgreSQL")
        conn = self._conn
        try:
            async with self._lock:
                cursor = await asyncio.wait_for(conn.execute(sql, params), timeout)
                return await asyncio.wait_for(cursor.fetchall(), timeout)
        except Exception:
            await self._perder()
            raise

    async def cerrar(self) -> None:
        await self._perder()
