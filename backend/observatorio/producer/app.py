"""Servicio productor (esqueleto 001): Kafka → topic → salud. USGS lo añade la feature 002."""

import logging

from aiokafka import AIOKafkaProducer

from observatorio.common.config import AjustesProductor
from observatorio.common.health import EstadoSalud, servidor_salud
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, ensure_topic, sonda_kafka
from observatorio.common.logging import registrar
from observatorio.common.parada import esperar, evento_de_parada, hasta_parada
from observatorio.common.retry import motivo_de, reintentar

_log = logging.getLogger("observatorio.producer")


async def _abrir_kafka(ajustes: AjustesProductor) -> AIOKafkaProducer:
    """Garantiza el topic y devuelve un productor iniciado (`acks=all`, idempotente)."""
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
    return productor


async def ejecutar(ajustes: AjustesProductor) -> None:
    estado = EstadoSalud(["kafka"])
    parada = evento_de_parada()
    registrar(_log, "iniciado", component="producer")
    servidor = await servidor_salud(estado, ajustes.health_port)
    productor = None
    try:
        # Los reintentos se abandonan si llega una orden de parada.
        productor, parado = await hasta_parada(
            reintentar(lambda: _abrir_kafka(ajustes), dependency="kafka", config=ajustes.backoff, logger=_log),
            parada,
        )
        if parado:
            return
        estado.marcar("kafka", True)
        registrar(_log, "listo", component="kafka")

        # Reposo con sonda periódica; la feature 002 sustituirá el reposo por el ciclo de USGS.
        sano = True
        while not await esperar(parada, ajustes.health_probe_interval_seconds):
            try:
                await sonda_kafka(productor.client.fetch_all_metadata)
            except Exception as exc:
                if sano:
                    registrar(_log, "error", nivel="WARNING", component="kafka", reason=motivo_de(exc))
                sano = False
            else:
                if not sano:
                    registrar(_log, "listo", component="kafka")
                sano = True
            estado.marcar("kafka", sano)
    finally:
        registrar(_log, "detenido", component="producer")
        servidor.close()
        if productor is not None:
            await cerrar_sin_error(productor)
