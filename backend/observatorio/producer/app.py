"""Servicio productor: mantiene Kafka y publica el feed USGS cada `POLL_INTERVAL_SECONDS`."""

import asyncio
import logging

from aiokafka import AIOKafkaProducer

from observatorio.common.config import AjustesProductor
from observatorio.common.db import Database
from observatorio.common.health import EstadoSalud, servidor_salud
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, ensure_topic, sonda_kafka
from observatorio.common.logging import registrar
from observatorio.common.parada import esperar, evento_de_parada
from observatorio.common.retry import motivo_de
from observatorio.common.supervisor import supervisar
from observatorio.producer.ciclo import asegurar_tablas, una_pasada
from observatorio.producer.feed import ErrorTransitorio

_log = logging.getLogger("observatorio.producer")


class SesionKafka:
    """El supervisor sustituye el productor al recrear la sesión; el bucle lee el vigente."""

    def __init__(self):
        self.productor: AIOKafkaProducer | None = None


async def _abrir_kafka(ajustes: AjustesProductor, sesion: SesionKafka) -> AIOKafkaProducer:
    admin = await abrir_admin(ajustes.kafka_bootstrap_servers)
    try:
        await ensure_topic(admin, ajustes.topic_live, ajustes.topic_partitions, ajustes.topic_retention_ms, _log)
    finally:
        await cerrar_sin_error(admin)
    productor = AIOKafkaProducer(
        bootstrap_servers=ajustes.kafka_bootstrap_servers,
        acks="all",
        enable_idempotence=True,
    )
    try:
        await productor.start()
    except BaseException:
        await cerrar_sin_error(productor)
        raise
    sesion.productor = productor
    return productor


async def _cerrar_kafka(productor, sesion: SesionKafka) -> None:
    if sesion.productor is productor:
        sesion.productor = None
    await cerrar_sin_error(productor)


async def _sondear(productor: AIOKafkaProducer) -> None:
    await sonda_kafka(productor.client.fetch_all_metadata)


async def _bucle(ajustes: AjustesProductor, sesion: SesionKafka, db: Database, parada: asyncio.Event) -> None:
    """Una pasada cuando hay Kafka y PostgreSQL. Un fallo de USGS no para el proceso."""
    espera = ajustes.retry_initial_seconds
    tablas_listas = False
    while not parada.is_set():
        if sesion.productor is None or not db.conectada:
            if await esperar(parada, 1):
                return
            continue
        try:
            if not tablas_listas:
                await asegurar_tablas(db)
                tablas_listas = True
            await una_pasada(ajustes, sesion.productor, db)
        except ErrorTransitorio as exc:
            registrar(_log, "reintento", component="usgs", reason=exc.motivo, wait_s=espera)
            if await esperar(parada, espera):
                return
            espera = min(espera * ajustes.retry_factor, ajustes.retry_max_seconds)
            continue
        except Exception as exc:
            registrar(_log, "error", nivel="ERROR", component="usgs", reason=motivo_de(exc))
            tablas_listas = False
        espera = ajustes.retry_initial_seconds
        if await esperar(parada, ajustes.poll_interval_seconds):
            return


async def ejecutar(ajustes: AjustesProductor) -> None:
    estado = EstadoSalud(["kafka", "postgres"])
    parada = evento_de_parada()
    registrar(_log, "iniciado", component="producer")
    servidor = await servidor_salud(estado, ajustes.health_port)
    db = Database.desde_ajustes(ajustes.postgres, ajustes.backoff, estado=estado)
    sesion = SesionKafka()

    async def abrir_db() -> Database:
        await db.conectar()
        return db

    tareas = {
        asyncio.create_task(
            supervisar(
                lambda: _abrir_kafka(ajustes, sesion),
                _sondear,
                "kafka",
                estado,
                ajustes,
                cerrar=lambda productor: _cerrar_kafka(productor, sesion),
                logger=_log,
            )
        ),
        asyncio.create_task(
            supervisar(
                abrir_db,
                lambda base: base.sonda(),
                "postgres",
                estado,
                ajustes,
                cerrar=Database.cerrar,
                logger=_log,
                registrar_listo=False,
            )
        ),
        asyncio.create_task(_bucle(ajustes, sesion, db, parada)),
    }
    espera_parada = asyncio.create_task(parada.wait())
    try:
        await asyncio.wait(tareas | {espera_parada}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for tarea in tareas | {espera_parada}:
            tarea.cancel()
        await asyncio.gather(*tareas, espera_parada, return_exceptions=True)
        registrar(_log, "detenido", component="producer")
        servidor.close()
        await db.cerrar()
