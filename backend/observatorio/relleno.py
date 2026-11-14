"""Relleno de la base con el histórico de las fuentes (feature 013, FR-010).

`python -m observatorio.relleno --desde 2025-01-01 [--hasta 2026-11-14T00:00:00] --magnitud-min 2.5
[--fuentes usgs,emsc]`

Publica en los topics por fuente (`eventos.usgs`, `eventos.emsc`) todos los terremotos del
intervalo, por tramos que caben en una consulta; desde ahí pasan por la misma fusión que el
directo. Marca lo publicado en `ingesta.publicadas`: repetirlo no republica nada.

Ninguna fuente avisa bien de que se pasa: USGS rechaza más de 20.000 filas y EMSC corta en
~10.000 sin decir nada. Por eso se cuenta antes (`/count`) y se parte el tramo hasta que cabe.
"""

import argparse
import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

TRAMO_MINIMO = timedelta(minutes=30)
DIRECTORIO = Path("/data/relleno")
HTTP_TIMEOUT_S = 180
REINTENTOS = 6
_log = logging.getLogger("observatorio.relleno")


class ErrorPlan(Exception):
    """Un tramo ya mínimo sigue sin caber en una consulta: no se puede rellenar sin truncar."""


@dataclass(frozen=True)
class Tramo:
    desde: datetime
    hasta: datetime
    eventos: int


def tramos_mensuales(desde: datetime, hasta: datetime) -> list[tuple[datetime, datetime]]:
    """Meses naturales (el primero y el último, recortados). El fin de uno es el inicio del siguiente."""
    tramos = []
    inicio = desde
    while inicio < hasta:
        siguiente_mes = (
            datetime(inicio.year + 1, 1, 1, tzinfo=timezone.utc)
            if inicio.month == 12
            else datetime(inicio.year, inicio.month + 1, 1, tzinfo=timezone.utc)
        )
        fin = min(siguiente_mes, hasta)
        tramos.append((inicio, fin))
        inicio = fin
    return tramos


def planificar(
    desde: datetime,
    hasta: datetime,
    contar: Callable[[datetime, datetime], int],
    tope: int,
    minimo: timedelta = TRAMO_MINIMO,
) -> list[Tramo]:
    """Tramos con como mucho `tope` eventos cada uno, en orden. Los vacíos no se incluyen.

    Empieza por meses y parte por la mitad mientras `contar` diga que no cabe. Lanza `ErrorPlan`
    si un tramo de `minimo` o menos sigue sin caber.
    """
    if not desde < hasta:
        raise ValueError("desde debe ser anterior a hasta")
    plan: list[Tramo] = []
    pendientes = list(reversed(tramos_mensuales(desde, hasta)))
    while pendientes:
        inicio, fin = pendientes.pop()
        eventos = contar(inicio, fin)
        if eventos <= tope:
            if eventos > 0:
                plan.append(Tramo(inicio, fin, eventos))
            continue
        if fin - inicio <= minimo:
            raise ErrorPlan(f"{inicio.isoformat()}–{fin.isoformat()} tiene {eventos} eventos (tope {tope})")
        medio = inicio + (fin - inicio) / 2
        pendientes.extend([(medio, fin), (inicio, medio)])  # se procesa antes la primera mitad
    return plan


# ── Red, Kafka y PostgreSQL ─────────────────────────────────────────────


def _con_reintentos(funcion, *args):
    """Reintenta un 429/5xx/corte de red con espera creciente; a la sexta, se rinde."""
    from observatorio.producer.feed import ErrorTransitorio

    espera = 2.0
    for intento in range(1, REINTENTOS + 1):
        try:
            return funcion(*args)
        except ErrorTransitorio as exc:
            if intento == REINTENTOS:
                raise
            from observatorio.common.logging import registrar

            registrar(_log, "reintento", component="relleno", reason=exc.motivo, attempt=intento, wait_s=espera)
            time.sleep(espera)
            espera = min(espera * 2, 60)


def _contador(fuente, magnitud_min: float, descargar):
    def contar(desde: datetime, hasta: datetime) -> int:
        status, cuerpo = _con_reintentos(descargar, fuente.url_recuento(desde, hasta, magnitud_min), HTTP_TIMEOUT_S)
        if status == 204:
            return 0
        if status != 200:
            raise RuntimeError(f"recuento de {fuente.nombre}: HTTP {status}")
        return fuente.leer_recuento(cuerpo)

    return contar


async def rellenar(ajustes, desde: datetime, hasta: datetime, magnitud_min: float, nombres: list[str], descargar=None) -> dict:
    """Rellena cada fuente de `nombres` en `[desde, hasta)`. Devuelve publicados por fuente."""
    from aiokafka import AIOKafkaProducer

    from observatorio.common.contrato import construir_mensaje
    from observatorio.common.db import Database
    from observatorio.common.kafka import abrir_admin, cerrar_sin_error, ensure_topic
    from observatorio.common.logging import registrar
    from observatorio.producer import ciclo
    from observatorio.producer.fuentes import fuente_por_nombre

    descargar = descargar or ciclo.descargar
    db = Database.desde_ajustes(ajustes.postgres, ajustes.backoff)
    await db.conectar()
    await ciclo.asegurar_tablas(db)
    admin = await abrir_admin(ajustes.kafka_bootstrap_servers)
    fuentes = [fuente_por_nombre(n, ajustes.usgs_feed_url, ajustes.emsc_url_base) for n in nombres]
    try:
        for f in fuentes:
            await ensure_topic(admin, f"eventos.{f.nombre}", ajustes.topic_partitions, ajustes.topic_retention_ms, _log)
    finally:
        await cerrar_sin_error(admin)
    productor = AIOKafkaProducer(bootstrap_servers=ajustes.kafka_bootstrap_servers, acks="all", enable_idempotence=True)
    await productor.start()
    totales: dict[str, int] = {}
    try:
        for fuente in fuentes:
            topic = f"eventos.{fuente.nombre}"
            plan = await asyncio.to_thread(planificar, desde, hasta, _contador(fuente, magnitud_min, descargar), fuente.tope_consulta)
            registrar(_log, "info", component="relleno", source=fuente.nombre, tramos=len(plan),
                      eventos=sum(t.eventos for t in plan), desde=desde.isoformat(), hasta=hasta.isoformat())
            totales[fuente.nombre] = 0
            for numero, tramo in enumerate(plan, 1):
                totales[fuente.nombre] += await _tramo(
                    ajustes, db, productor, fuente, topic, tramo, magnitud_min, descargar, numero, len(plan),
                    construir_mensaje, registrar, ciclo,
                )
    finally:
        await productor.stop()
        await db.cerrar()
    return totales


async def _tramo(ajustes, db, productor, fuente, topic, tramo: Tramo, magnitud_min, descargar, numero, de,
                 construir_mensaje, registrar, ciclo) -> int:
    url = fuente.url_consulta(tramo.desde, tramo.hasta, magnitud_min)
    status, cuerpo = await asyncio.to_thread(_con_reintentos, descargar, url, HTTP_TIMEOUT_S)
    if status == 204:
        await ciclo._anotar_consulta(db, url, fuente.nombre, http_status=204, bytes=0, features=0, publicados=0)
        return 0
    if status != 200:
        raise RuntimeError(f"{fuente.nombre} {tramo.desde.isoformat()}: HTTP {status}")
    features = json.loads(cuerpo)["features"]
    if len(features) < tramo.eventos * 0.98:
        # La fuente devolvió bastantes menos de los que contó: posible truncado. Se avisa, no se oculta.
        registrar(_log, "error", nivel="WARNING", component="relleno", source=fuente.nombre, reason="menos_de_los_contados",
                  contados=tramo.eventos, devueltos=len(features), desde=tramo.desde.isoformat())
    # Original antes de transformar (constitución IV): un fichero por tramo, idempotente.
    carpeta = DIRECTORIO / fuente.nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{tramo.desde:%Y%m%dT%H%M%S}_{tramo.hasta:%Y%m%dT%H%M%S}_m{magnitud_min:g}.json"
    (carpeta / nombre).write_bytes(cuerpo)

    ids = sorted({x["id"] for x in features if isinstance(x, dict) and isinstance(x.get("id"), str)})
    filas = await db.consultar(ciclo._SQL_PUBLICADAS, (fuente.nombre, ids), timeout=60) if ids else []
    clasificacion = fuente.clasificar(features, {(fila[0], fila[1]) for fila in filas})
    ahora = datetime.now(timezone.utc)
    # Se envían todos y se espera a todos los acuses; solo entonces se marcan (constitución III).
    pendientes = []
    for evento in clasificacion.publicar:
        clave, valor = construir_mensaje(evento, fuente.nombre, "live", ahora)
        pendientes.append(await productor.send(topic, value=valor, key=clave))
    await asyncio.gather(*pendientes)
    marcas = [(e["id"], fuente.version_de(e), fuente.nombre) for e in clasificacion.publicar]
    if marcas:
        async with db.transaccion(timeout=120) as conn:
            async with conn.cursor() as cur:
                await cur.executemany(ciclo._SQL_MARCAR, marcas)
    consulta_id = await ciclo._anotar_consulta(
        db, url, fuente.nombre, http_status=status, bytes=len(cuerpo), features=len(features),
        publicados=len(marcas), omitidos=clasificacion.omitidos, excluidos=len(clasificacion.exclusiones),
    )
    if clasificacion.exclusiones:
        async with db.transaccion(timeout=60) as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    ciclo._SQL_EXCLUSION,
                    [(consulta_id, x.event_id, x.tipo, x.motivo, fuente.nombre) for x in clasificacion.exclusiones],
                )
    registrar(_log, "publicado", component="relleno", source=fuente.nombre, tramo=f"{numero}/{de}",
              desde=tramo.desde.isoformat(), publicados=len(marcas), omitidos=clasificacion.omitidos,
              excluidos=len(clasificacion.exclusiones))
    return len(marcas)


def _instante(texto: str) -> datetime:
    valor = datetime.fromisoformat(texto)
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    from observatorio.common.config import ajustes_productor, cargar_o_salir
    from observatorio.common.logging import configurar_logging, registrar

    parser = argparse.ArgumentParser(prog="python -m observatorio.relleno", description=__doc__.splitlines()[0])
    parser.add_argument("--desde", default="2025-01-01", help="inicio UTC (incluido), p. ej. 2025-01-01")
    parser.add_argument("--hasta", default=None, help="fin UTC (excluido); por defecto, ahora")
    parser.add_argument("--magnitud-min", type=float, default=2.5)
    parser.add_argument("--fuentes", default="usgs,emsc", help="lista separada por comas")
    args = parser.parse_args(argv)
    ajustes = cargar_o_salir("relleno", ajustes_productor)
    configurar_logging("relleno", ajustes.log_level, ajustes.secretos())
    desde = _instante(args.desde)
    hasta = _instante(args.hasta) if args.hasta else datetime.now(timezone.utc).replace(microsecond=0)
    nombres = [n.strip() for n in args.fuentes.split(",") if n.strip()]
    inicio = time.monotonic()
    totales = asyncio.run(rellenar(ajustes, desde, hasta, args.magnitud_min, nombres))
    registrar(_log, "listo", component="relleno", **{f"publicados_{k}": v for k, v in totales.items()},
              segundos=round(time.monotonic() - inicio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
