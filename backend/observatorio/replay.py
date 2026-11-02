"""Reproducción acelerada de una selección histórica por el topic de replay.

Mantiene el tiempo original del evento (`properties.time`) y usa `ingested_at`
como tiempo de reproducción. Añade un duplicado y una revisión controlados.
"""

import asyncio
import copy
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from observatorio.common.config import ajustes_productor, cargar_o_salir
from observatorio.common.contrato import construir_mensaje
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, ensure_topic
from observatorio.common.logging import configurar_logging, registrar
from observatorio.common.retry import motivo_de, reintentar
from observatorio.common.tiempo import iso_utc, ms_a_datetime
from observatorio.producer.feed import SOURCE_USGS
from observatorio.producer.smoke import _preparar

_log = logging.getLogger("observatorio.replay")
ETIQUETA = "REPRODUCCIÓN"


def cargar_eventos(directorio: Path, anio: int) -> list:
    ruta = directorio / str(anio) / "eventos.geojson"
    if not ruta.is_file():
        raise FileNotFoundError(f"no está el histórico: {ruta}. Ejecuta python -m observatorio.historico")
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    features = documento["features"]
    return sorted(features, key=lambda evento: evento["properties"]["time"])


def preparar(eventos: list, limite: int) -> list[tuple[str, dict]]:
    """Selección ordenada, más una copia exacta y una revisión del primero."""
    utilizables = [evento for evento in eventos if _usable(evento)]
    utilizables.sort(key=lambda evento: evento["properties"]["time"])
    seleccion = utilizables[:limite]
    if not seleccion:
        raise ValueError("el histórico no tiene eventos utilizables")
    primero = seleccion[0]
    revision = copy.deepcopy(primero)
    revision["properties"]["updated"] = primero["properties"]["updated"] + 60_000
    return (
        [("normal", evento) for evento in seleccion]
        + [("duplicado", primero), ("revision", revision)]
    )


def _usable(evento: dict) -> bool:
    propiedades = evento.get("properties") or {}
    return isinstance(evento.get("id"), str) and isinstance(propiedades.get("time"), int) and isinstance(propiedades.get("updated"), int)


async def _publicar(ajustes, plan: list[tuple[str, dict]], pausa: float) -> None:
    admin = await abrir_admin(ajustes.kafka_bootstrap_servers)
    try:
        await ensure_topic(admin, ajustes.topic_replay, ajustes.topic_partitions, ajustes.topic_retention_ms, _log)
    finally:
        await cerrar_sin_error(admin)
    productor = await reintentar(lambda: _preparar(ajustes), dependency="kafka", config=ajustes.backoff, logger=_log)
    try:
        for caso, evento in plan:
            ahora = datetime.now(timezone.utc)
            clave, valor = construir_mensaje(evento, SOURCE_USGS, "replay", ahora)
            metadatos = await productor.send_and_wait(ajustes.topic_replay, value=valor, key=clave)
            registrar(
                _log,
                "publicado",
                etiqueta=ETIQUETA,
                caso=caso,
                event_id=evento["id"],
                updated=evento["properties"]["updated"],
                ocurrencia=iso_utc_ms(evento["properties"]["time"]),
                ingested_at=iso_utc(ahora),
                topic=metadatos.topic,
                offset=metadatos.offset,
            )
            if pausa:
                await asyncio.sleep(pausa)
    finally:
        await cerrar_sin_error(productor)


def iso_utc_ms(milisegundos: int) -> str:
    return iso_utc(ms_a_datetime(milisegundos))


def main() -> int:
    ajustes = cargar_o_salir("replay", ajustes_productor)
    configurar_logging("replay", ajustes.log_level, ajustes.secretos())
    directorio = Path(os.environ.get("HISTORICO_DIR", "/data/historico"))
    anio = int(os.environ.get("HISTORICO_ANIO", "2025"))
    limite = int(os.environ.get("REPLAY_LIMITE", "40"))
    pausa = float(os.environ.get("REPLAY_PAUSA_SECONDS", "0.2"))
    try:
        plan = preparar(cargar_eventos(directorio, anio), limite)
        asyncio.run(_publicar(ajustes, plan, pausa))
    except Exception as exc:
        registrar(_log, "error", nivel="ERROR", etiqueta=ETIQUETA, reason=motivo_de(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
