"""Utilidades de Kafka: creación del topic, espera del topic y sonda de metadatos (R-04, R-05)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

from aiokafka.admin import NewTopic

from observatorio.common.logging import registrar
from observatorio.common.retry import Backoff, FalloDependencia, reintentar

_log = logging.getLogger("observatorio.kafka")

UN_DIA_MS = 86_400_000

_ERROR_TOPIC_YA_EXISTE = 36


class ErrorCreacionTopic(Exception):
    """El broker rechazó la creación del topic con un código distinto de «ya existe»."""


def configuracion_topic(retention_ms: int) -> dict[str, str]:
    """`retention.ms` y `segment.ms`: Kafka solo borra segmentos cerrados (R-05)."""
    return {
        "retention.ms": str(retention_ms),
        "segment.ms": str(min(retention_ms, UN_DIA_MS)),
    }


def interpretar_creacion(respuesta, topic: str) -> str:
    """«creado» o «existe». Crear un topic existente no lanza: devuelve el error 36 (R-05)."""
    for entrada in respuesta.topic_errors:
        nombre, codigo = entrada[0], entrada[1]
        if nombre != topic:
            continue
        if codigo == 0:
            return "creado"
        if codigo == _ERROR_TOPIC_YA_EXISTE:
            return "existe"
        detalle = entrada[2] if len(entrada) > 2 else None
        raise ErrorCreacionTopic(f"error_code={codigo} topic={topic} detalle={detalle}")
    raise ErrorCreacionTopic(f"la respuesta no incluye el topic {topic}")


def topic_listado(nombres: Iterable[str], topic: str) -> bool:
    return topic in set(nombres)


async def ensure_topic(
    admin,
    topic: str,
    particiones: int,
    retention_ms: int,
    logger: logging.Logger = _log,
) -> str:
    """Crea el topic con su retención. Si ya existe no lo toca (la reconciliación llega en US4)."""
    nuevo = NewTopic(
        name=topic,
        num_partitions=particiones,
        replication_factor=1,
        topic_configs=configuracion_topic(retention_ms),
    )
    resultado = interpretar_creacion(await admin.create_topics([nuevo]), topic)
    registrar(
        logger,
        "listo",
        component="topic",
        action="topic_creado" if resultado == "creado" else "topic_existente",
        topic=topic,
        partitions=particiones,
        retention_ms=retention_ms,
    )
    return resultado


async def wait_for_topic(
    admin,
    topic: str,
    config: Backoff,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    logger: logging.Logger = _log,
) -> None:
    """Espera con backoff a que el productor haya creado el topic (el consumidor nunca lo crea)."""

    async def comprobar() -> None:
        if not topic_listado(await admin.list_topics(), topic):
            raise FalloDependencia("topic_no_existe")

    await reintentar(comprobar, dependency="topic", config=config, sleep=sleep, logger=logger)


async def sonda_kafka(metadatos: Callable[[], Awaitable], timeout: float = 3.0):
    """Pide metadatos al broker con límite de tiempo; lanza si no responde."""
    return await asyncio.wait_for(metadatos(), timeout)
