"""Prueba de humo: `python -m observatorio.producer.smoke [--repeat N] [--unico]` (R-11).

Publica el evento sintético con acuse (`acks=all`, idempotente). `result=publicado` solo se
escribe cuando `send_and_wait` ha devuelto, es decir, después del acuse de Kafka (FR-014).
"""

import argparse
import asyncio
import logging
import sys

from aiokafka import AIOKafkaProducer

from observatorio.common.config import AjustesProductor, ajustes_productor, cargar_o_salir
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, ensure_topic
from observatorio.common.logging import configurar_logging, registrar
from observatorio.common.retry import motivo_de, reintentar
from observatorio.producer.evento_sintetico import UPDATED_MS, mensaje_sintetico

_log = logging.getLogger("observatorio.smoke")


async def _preparar(ajustes: AjustesProductor) -> AIOKafkaProducer:
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


async def _publicar(ajustes: AjustesProductor, repeticiones: int, unico: bool) -> None:
    # Con Kafka caído se reintenta (con log) hasta agotar SMOKE_TIMEOUT_SECONDS.
    productor = await reintentar(lambda: _preparar(ajustes), dependency="kafka", config=ajustes.backoff, logger=_log)
    try:
        for _ in range(repeticiones):
            clave, valor = mensaje_sintetico(unico=unico)
            metadatos = await productor.send_and_wait(ajustes.topic_live, value=valor, key=clave)
            # Este registro va DESPUÉS del acuse: send_and_wait devuelve cuando Kafka lo confirmó.
            registrar(
                _log,
                "publicado",
                event_id=clave.decode("utf-8"),
                updated=UPDATED_MS,
                topic=metadatos.topic,
                partition=metadatos.partition,
                offset=metadatos.offset,
            )
    finally:
        await cerrar_sin_error(productor)


async def ejecutar(ajustes: AjustesProductor, repeticiones: int, unico: bool) -> int:
    try:
        await asyncio.wait_for(_publicar(ajustes, repeticiones, unico), ajustes.smoke_timeout_seconds)
    except asyncio.TimeoutError:
        registrar(_log, "error", nivel="ERROR", reason="sin_acuse", timeout_s=ajustes.smoke_timeout_seconds)
        return 1
    except Exception as exc:
        registrar(_log, "error", nivel="ERROR", reason=motivo_de(exc))
        return 1
    return 0


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m observatorio.producer.smoke", description=__doc__)
    analizador.add_argument("--repeat", type=int, default=1, metavar="N", help="publica N veces la misma versión")
    analizador.add_argument("--unico", action="store_true", help="id con la hora UTC: crea otro evento sintético")
    args = analizador.parse_args(argv)
    if args.repeat < 1:
        analizador.error("--repeat debe ser >= 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    ajustes = cargar_o_salir("producer", ajustes_productor)
    configurar_logging("producer", ajustes.log_level, ajustes.secretos())
    return asyncio.run(ejecutar(ajustes, args.repeat, args.unico))


if __name__ == "__main__":
    sys.exit(main())
