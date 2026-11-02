"""Servicio productor (esqueleto 001): Kafka → topic → salud. USGS lo añade la feature 002."""

import logging

from aiokafka import AIOKafkaProducer

from observatorio.common.config import AjustesProductor
from observatorio.common.health import EstadoSalud, servidor_salud
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, ensure_topic, sonda_kafka
from observatorio.common.logging import registrar
from observatorio.common.parada import evento_de_parada, hasta_parada
from observatorio.common.supervisor import supervisar

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


async def _sondear(productor: AIOKafkaProducer) -> None:
    """Pide metadatos al broker con límite de tiempo; lanza si no responde."""
    await sonda_kafka(productor.client.fetch_all_metadata)


async def ejecutar(ajustes: AjustesProductor) -> None:
    estado = EstadoSalud(["kafka"])
    parada = evento_de_parada()
    registrar(_log, "iniciado", component="producer")
    servidor = await servidor_salud(estado, ajustes.health_port)
    try:
        # El supervisor abre la sesión (topic + productor) con backoff, la sondea y, tras
        # PROBE_FALLOS_REINICIO fallos seguidos, la recrea volviendo a ejecutar `ensure_topic`.
        # La feature 002 sustituirá este reposo por el ciclo de USGS usando la misma sesión.
        await hasta_parada(
            supervisar(
                lambda: _abrir_kafka(ajustes),
                _sondear,
                "kafka",
                estado,
                ajustes,
                cerrar=cerrar_sin_error,
                logger=_log,
            ),
            parada,
        )
    finally:
        registrar(_log, "detenido", component="producer")
        servidor.close()