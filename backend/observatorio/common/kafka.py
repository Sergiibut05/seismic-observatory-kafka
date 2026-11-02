"""Utilidades de Kafka: creación y reconciliación del topic, espera del topic y sonda (R-04, R-05)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.admin.config_resource import ConfigResource, ConfigResourceType

from observatorio.common.logging import registrar
from observatorio.common.retry import Backoff, FalloDependencia, reintentar

_log = logging.getLogger("observatorio.kafka")

UN_DIA_MS = 86_400_000

_ERROR_TOPIC_YA_EXISTE = 36


class ErrorCreacionTopic(Exception):
    """El broker rechazó la creación del topic con un código distinto de «ya existe»."""


class ErrorReconciliacionTopic(Exception):
    """El broker rechazó leer o alterar la configuración de un topic existente."""


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


@dataclass(frozen=True)
class PlanReconciliacion:
    """Qué hacer con un topic existente: `sin_cambios` o `alterar` (con los pares que difieren)."""

    accion: str
    cambios: dict[str, str] = field(default_factory=dict)
    avisos: tuple[str, ...] = ()


def plan_reconciliacion(
    actual: dict,
    deseado: dict,
    particiones_actuales: int | None = None,
    particiones_deseadas: int | None = None,
) -> PlanReconciliacion:
    """Compara `retention.ms` y `segment.ms` (como texto) y las particiones. Función pura (R-05).

    Las particiones nunca se proponen para cambiar: no se pueden reducir y aumentarlas altera el
    reparto por clave. Solo se avisa con `particiones_distintas`.
    """
    cambios = {clave: str(valor) for clave, valor in deseado.items() if str(actual.get(clave)) != str(valor)}
    avisos: tuple[str, ...] = ()
    if (
        particiones_actuales is not None
        and particiones_deseadas is not None
        and particiones_actuales != particiones_deseadas
    ):
        avisos = ("particiones_distintas",)
    return PlanReconciliacion("alterar" if cambios else "sin_cambios", cambios, avisos)


def _codigo_de_error(entrada, topic: str, operacion: str) -> None:
    codigo = entrada[0]
    if codigo != 0:
        mensaje = entrada[1] if len(entrada) > 1 else None
        raise ErrorReconciliacionTopic(f"{operacion} error_code={codigo} topic={topic} detalle={mensaje}")


async def leer_estado_topic(admin, topic: str) -> tuple[dict[str, str], int]:
    """Configuración efectiva (`retention.ms`, `segment.ms`) y número de particiones del topic."""
    respuestas = await admin.describe_configs([ConfigResource(ConfigResourceType.TOPIC, topic)])
    for respuesta in respuestas:
        for recurso in respuesta.resources:
            # (error_code, error_message, resource_type, resource_name, config_entries)
            if recurso[3] != topic:
                continue
            _codigo_de_error(recurso, topic, "describe_configs")
            configuracion = {entrada[0]: entrada[1] for entrada in recurso[4]}
            descripcion = await admin.describe_topics([topic])
            particiones = len(descripcion[0]["partitions"]) if descripcion else 0
            return {k: configuracion.get(k) for k in ("retention.ms", "segment.ms")}, particiones
    raise ErrorReconciliacionTopic(f"describe_configs no devolvió el topic {topic}")


async def alterar_configuracion(admin, topic: str, deseado: dict[str, str]) -> None:
    """`alter_configs` (legacy, no incremental): se envía el conjunto completo (R-05)."""
    respuestas = await admin.alter_configs([ConfigResource(ConfigResourceType.TOPIC, topic, dict(deseado))])
    for respuesta in respuestas:
        for recurso in respuesta.resources:
            # (error_code, error_message, resource_type, resource_name)
            if recurso[3] == topic:
                _codigo_de_error(recurso, topic, "alter_configs")


async def ensure_topic(
    admin,
    topic: str,
    particiones: int,
    retention_ms: int,
    logger: logging.Logger = _log,
) -> str:
    """Crea el topic o, si existe, lo reconcilia con `.env`. Devuelve `creado`, `reconciliado` o `conforme`.

    No se verifica con `describe_configs` justo después de alterar: puede devolver el valor anterior
    durante ~1 s (R-05). La comprobación se hace con `kafka-configs.sh` en el quickstart.
    """
    deseado = configuracion_topic(retention_ms)
    nuevo = NewTopic(
        name=topic,
        num_partitions=particiones,
        replication_factor=1,
        topic_configs=deseado,
    )
    resultado = interpretar_creacion(await admin.create_topics([nuevo]), topic)
    accion = "topic_creado"
    final = "creado"
    particiones_reales = particiones
    if resultado == "existe":
        actual, particiones_actuales = await leer_estado_topic(admin, topic)
        particiones_reales = particiones_actuales  # el log refleja lo que hay, no lo configurado
        plan = plan_reconciliacion(actual, deseado, particiones_actuales, particiones)
        for aviso in plan.avisos:
            registrar(
                logger,
                "info",
                nivel="WARNING",
                component="topic",
                action=aviso,
                topic=topic,
                partitions_actuales=particiones_actuales,
                partitions_configuradas=particiones,
            )
        if plan.accion == "alterar":
            await alterar_configuracion(admin, topic, deseado)
            accion, final = "topic_reconciliado", "reconciliado"
        else:
            accion, final = "topic_conforme", "conforme"
    registrar(
        logger,
        "listo",
        component="topic",
        action=accion,
        topic=topic,
        partitions=particiones_reales,
        retention_ms=retention_ms,
    )
    return final

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


async def abrir_admin(bootstrap_servers: str):
    """Cliente administrativo ya iniciado; si no conecta se cierra y se relanza el error."""
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
    try:
        await admin.start()
    except BaseException:
        await cerrar_sin_error(admin)
        raise
    return admin


async def cerrar_sin_error(recurso) -> None:
    """Cierra un cliente aiokafka: productor y consumidor usan `stop()`, el admin usa `close()`."""
    cerrar = getattr(recurso, "stop", None) or recurso.close
    try:
        await asyncio.wait_for(cerrar(), 5)
    except Exception:
        pass


async def sonda_kafka(metadatos: Callable[[], Awaitable], timeout: float = 3.0):
    """Pide metadatos al broker con límite de tiempo; lanza si no responde."""
    return await asyncio.wait_for(metadatos(), timeout)
