"""Servicio consumidor (esqueleto 001): catálogo → PostgreSQL → topic → suscripción.

El bucle de consumo (validar, guardar, confirmar offset) se completa en la historia US2.
"""

import logging

from aiokafka import AIOKafkaConsumer

from observatorio.common.catalogo import CatalogoError, cargar_catalogo
from observatorio.common.config import AjustesConsumidor
from observatorio.common.db import Database
from observatorio.common.health import EstadoSalud, servidor_salud
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, sonda_kafka, wait_for_topic
from observatorio.common.logging import registrar
from observatorio.common.parada import esperar, evento_de_parada, hasta_parada
from observatorio.common.retry import motivo_de, reintentar

_log = logging.getLogger("observatorio.consumer")


async def _esperar_topic(ajustes: AjustesConsumidor) -> None:
    admin = await reintentar(
        lambda: abrir_admin(ajustes.kafka_bootstrap_servers),
        dependency="kafka",
        config=ajustes.backoff,
        logger=_log,
    )
    try:
        await wait_for_topic(admin, ajustes.topic_live, ajustes.backoff, logger=_log)
    finally:
        await cerrar_sin_error(admin)


async def _abrir_consumidor(ajustes: AjustesConsumidor) -> AIOKafkaConsumer:
    consumidor = AIOKafkaConsumer(
        ajustes.topic_live,
        bootstrap_servers=ajustes.kafka_bootstrap_servers,
        group_id=ajustes.consumer_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    try:
        await consumidor.start()
    except BaseException:
        await cerrar_sin_error(consumidor)
        raise
    return consumidor


async def ejecutar(ajustes: AjustesConsumidor) -> None:
    estado = EstadoSalud(["catalogo", "kafka", "postgres"])
    parada = evento_de_parada()
    registrar(_log, "iniciado", component="consumer")
    servidor = await servidor_salud(estado, ajustes.health_port)
    db = Database.desde_ajustes(ajustes.postgres, ajustes.backoff, estado=estado)
    consumidor = None
    try:
        # El catálogo se valida antes de conectar con PostgreSQL o Kafka (R-18).
        try:
            catalogo = cargar_catalogo(ajustes.catalogo_path)
        except CatalogoError as exc:
            registrar(
                _log,
                "error",
                nivel="ERROR",
                component="catalogo",
                motivo=exc.motivo,
                fuente=ajustes.catalogo_path,
                detalle=exc.detalle,
            )
            # Sin catálogo no se consume ni se conecta; el proceso sigue vivo y no reintenta la lectura.
            await parada.wait()
            return
        registrar(
            _log,
            "listo",
            component="catalogo",
            paises=catalogo.total,
            fuente=catalogo.fuente,
            geometrias_invalidas=catalogo.geometrias_invalidas,
        )
        estado.marcar("catalogo", True)

        _, parado = await hasta_parada(db.conectar(), parada)
        if parado:
            return

        _, parado = await hasta_parada(_esperar_topic(ajustes), parada)
        if parado:
            return
        consumidor, parado = await hasta_parada(
            reintentar(lambda: _abrir_consumidor(ajustes), dependency="kafka", config=ajustes.backoff, logger=_log),
            parada,
        )
        if parado:
            return
        estado.marcar("kafka", True)
        registrar(_log, "listo", component="kafka", topic=ajustes.topic_live, group=ajustes.consumer_group)

        # US1: el consumidor está suscrito pero no lee mensajes ni confirma offsets todavía.
        while not await esperar(parada, ajustes.health_probe_interval_seconds):
            await db.sonda()
            try:
                await sonda_kafka(consumidor.topics)
                estado.marcar("kafka", True)
            except Exception as exc:
                registrar(_log, "error", nivel="WARNING", component="kafka", reason=motivo_de(exc))
                estado.marcar("kafka", False)
    finally:
        registrar(_log, "detenido", component="consumer")
        servidor.close()
        if consumidor is not None:
            await cerrar_sin_error(consumidor)
        await db.cerrar()
