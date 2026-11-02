"""Servicio consumidor: catálogo → PostgreSQL → topic → bucle de consumo con commit manual.

Garantía de la Constitución III: por registro, `validar → transacción (versión o cuarentena) →
COMMIT → log → commit del offset`. El offset solo se confirma después del commit de PostgreSQL.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer, TopicPartition

from observatorio.common.catalogo import SIN_PAIS, CatalogoError, IndicePaises, cargar_catalogo, construir_indice
from observatorio.common.config import AjustesConsumidor
from observatorio.common.db import Database, SinConexion
from observatorio.common.health import EstadoSalud, servidor_salud
from observatorio.common.kafka import abrir_admin, cerrar_sin_error, sonda_kafka, wait_for_topic
from observatorio.common.logging import registrar
from observatorio.common.parada import esperar, evento_de_parada
from observatorio.common.retry import Backoff, esperas, motivo_de, reintentar
from observatorio.common.supervisor import supervisar
from observatorio.consumer.calidad import Contenido, evaluar
from observatorio.consumer.decision import Aceptar, clasificar_error_bd, decidir, resultado_escritura
from observatorio.consumer.persistencia import asegurar_modelo, guardar_cuarentena, guardar_version

_log = logging.getLogger("observatorio.consumer")

# El consumidor lee el topic live y el de reproducción. El modo sale del topic.
MODO_POR_DEFECTO = "live"


async def _esperar_topic(ajustes: AjustesConsumidor) -> None:
    admin = await reintentar(
        lambda: abrir_admin(ajustes.kafka_bootstrap_servers),
        dependency="kafka",
        config=ajustes.backoff,
        logger=_log,
    )
    try:
        await wait_for_topic(admin, ajustes.topic_live, ajustes.backoff, logger=_log)
        await wait_for_topic(admin, ajustes.topic_replay, ajustes.backoff, logger=_log)
    finally:
        await cerrar_sin_error(admin)


async def _abrir_consumidor(ajustes: AjustesConsumidor) -> AIOKafkaConsumer:
    consumidor = AIOKafkaConsumer(
        ajustes.topic_live,
        ajustes.topic_replay,
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


async def procesar_registro(
    db: Database,
    registro,
    logger: logging.Logger = _log,
    modo: str = MODO_POR_DEFECTO,
    indice: IndicePaises | None = None,
) -> str:
    """Decide, escribe en una transacción y registra el resultado. Devuelve el `result`.

    Lanza ante fallos de conexión o errores no clasificados: quien llama reintenta el mismo registro.
    """
    posicion = {"topic": registro.topic, "partition": registro.partition, "offset": registro.offset}
    decision = decidir(registro, modo)

    if isinstance(decision, Aceptar):
        version = decision.version
        contenido = evaluar(version.mensaje)
        if not isinstance(contenido, Contenido):
            await guardar_cuarentena(db, contenido.motivo, contenido.detalle, registro)
            registrar(
                logger,
                "rechazado",
                nivel="WARNING",
                event_id=version.event_id,
                updated=version.updated_ms,
                motivo=contenido.motivo,
                **posicion,
            )
            return "rechazado"
        codigo, nombre = indice.asignar(contenido.longitud, contenido.latitud) if indice is not None else (None, SIN_PAIS)
        try:
            filas = await guardar_version(
                db,
                version,
                registro,
                decision.esquema,
                contenido=contenido,
                pais_codigo=codigo,
                pais_nombre=nombre,
            )
        except Exception as exc:
            if clasificar_error_bd(exc) != "cuarentena":
                raise
            # Error de dato: la transacción ya se revirtió; se guarda en otra (R-09).
            detalle = f"sqlstate={getattr(exc, 'sqlstate', None) or type(exc).__name__}"
            await guardar_cuarentena(db, "no_almacenable", detalle, registro)
            registrar(
                logger,
                "rechazado",
                nivel="WARNING",
                event_id=version.event_id,
                updated=version.updated_ms,
                motivo="no_almacenable",
                detalle=detalle,
                **posicion,
            )
            return "rechazado"
        resultado = resultado_escritura(filas)
        extra = {"reason": "duplicado"} if resultado == "omitido" else {}
        if modo == "replay":
            extra["etiqueta"] = "REPRODUCCIÓN"
        registrar(
            logger,
            resultado,
            event_id=version.event_id,
            updated=version.updated_ms,
            **extra,
            **posicion,
            pais=nombre,
        )
        return resultado

    await guardar_cuarentena(db, decision.motivo, decision.detalle, registro)
    registrar(
        logger,
        "rechazado",
        nivel="WARNING",
        event_id=decision.event_id,
        updated=decision.updated,
        motivo=decision.motivo,
        **posicion,
    )
    return "rechazado"


def _es_error_de_conexion(exc: BaseException) -> bool:
    return clasificar_error_bd(exc) == "reintentar" or isinstance(exc, (SinConexion, TimeoutError, OSError))


async def procesar_con_reintentos(
    db: Database,
    registro,
    config: Backoff,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    logger: logging.Logger = _log,
    modo: str = MODO_POR_DEFECTO,
    indice: IndicePaises | None = None,
) -> str:
    """Reintenta el MISMO registro hasta lograrlo: nunca avanza, descarta ni confirma en silencio."""
    secuencia = esperas(config.inicial, config.factor, config.tope)
    intento = 0
    while True:
        try:
            return await procesar_registro(db, registro, logger, modo, indice)
        except Exception as exc:
            intento += 1
            espera = next(secuencia)
            if _es_error_de_conexion(exc):
                registrar(
                    logger,
                    "reintento",
                    dependency="postgres",
                    attempt=intento,
                    wait_s=espera,
                    reason=motivo_de(exc),
                    topic=registro.topic,
                    partition=registro.partition,
                    offset=registro.offset,
                )
                await sleep(espera)
                if not db.conectada:
                    await db.conectar()
            else:
                registrar(
                    logger,
                    "error",
                    nivel="ERROR",
                    reason=motivo_de(exc),
                    attempt=intento,
                    wait_s=espera,
                    topic=registro.topic,
                    partition=registro.partition,
                    offset=registro.offset,
                    exc_info=exc,
                )
                await sleep(espera)


async def confirmar_offset(consumidor, registro, logger: logging.Logger = _log) -> bool:
    """Confirma `offset + 1` (el siguiente a leer). Un fallo se registra y el registro se reentregará."""
    particion = TopicPartition(registro.topic, registro.partition)
    try:
        await consumidor.commit({particion: registro.offset + 1})
    except Exception as exc:
        registrar(
            logger,
            "error",
            nivel="ERROR",
            component="kafka",
            action="commit_offset",
            reason=motivo_de(exc),
            topic=registro.topic,
            partition=registro.partition,
            offset=registro.offset,
        )
        return False
    return True


class SesionConsumo:
    """Referencia al `AIOKafkaConsumer` vigente: el supervisor lo sustituye al recrear la sesión."""

    def __init__(self):
        self.consumidor = None


# Cada cuánto el bucle revisa si el supervisor ha recreado el consumidor mientras esperaba un mensaje.
ESPERA_LECTURA = 2.0


async def _abrir_sesion_kafka(ajustes: AjustesConsumidor, sesion: SesionConsumo) -> AIOKafkaConsumer:
    """Espera el topic y abre el consumidor; se vuelve a llamar al recrear la sesión (T045)."""
    await _esperar_topic(ajustes)
    consumidor = await _abrir_consumidor(ajustes)
    sesion.consumidor = consumidor
    return consumidor


async def _cerrar_sesion_kafka(consumidor, sesion: SesionConsumo) -> None:
    if sesion.consumidor is consumidor:
        sesion.consumidor = None
    await cerrar_sin_error(consumidor)


async def _consumir(
    ajustes: AjustesConsumidor,
    sesion: SesionConsumo,
    db: Database,
    parada: asyncio.Event,
    indice: IndicePaises | None = None,
) -> None:
    tabla_lista = False
    while not parada.is_set():
        consumidor = sesion.consumidor
        # Sin consumidor o sin PostgreSQL no se lee: así no se avanza ni se acumula nada en memoria.
        if consumidor is None or not db.conectada:
            await esperar(parada, 0.5)
            continue
        if not tabla_lista:
            try:
                relleno = await asegurar_modelo(db, indice)
            except Exception as exc:
                registrar(_log, "error", nivel="ERROR", component="estado", reason=motivo_de(exc))
                await esperar(parada, 1)
                continue
            registrar(_log, "listo", component="estado", **{f"versiones_{esquema}": n for esquema, n in relleno.items()})
            tabla_lista = True
        try:
            registro = await asyncio.wait_for(consumidor.getone(), ESPERA_LECTURA)
        except asyncio.TimeoutError:
            continue  # sin mensajes: se revisa si la sesión sigue siendo la misma
        except Exception as exc:
            if sesion.consumidor is not consumidor:
                continue  # el supervisor lo cerró para recrearlo: no es un error nuevo
            registrar(_log, "error", nivel="ERROR", component="kafka", action="lectura", reason=motivo_de(exc))
            await esperar(parada, 1)
            continue
        await procesar_con_reintentos(
            db,
            registro,
            ajustes.backoff,
            modo="replay" if registro.topic == getattr(ajustes, "topic_replay", None) else MODO_POR_DEFECTO,
            indice=indice,
        )
        await confirmar_offset(consumidor, registro)


async def _sondear_kafka(consumidor) -> None:
    await sonda_kafka(consumidor.topics)


async def ejecutar(ajustes: AjustesConsumidor) -> None:
    estado = EstadoSalud(["catalogo", "kafka", "postgres"])
    parada = evento_de_parada()
    registrar(_log, "iniciado", component="consumer")
    servidor = await servidor_salud(estado, ajustes.health_port)
    db = Database.desde_ajustes(ajustes.postgres, ajustes.backoff, estado=estado)
    sesion = SesionConsumo()
    try:
        # El catálogo se valida antes de conectar con PostgreSQL o Kafka (R-18).
        try:
            catalogo = cargar_catalogo(ajustes.catalogo_path)
            indice = construir_indice(ajustes.catalogo_path)
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

        async def abrir_db() -> Database:
            await db.conectar()
            return db

        async def sondear_db(base: Database) -> bool:
            return await base.sonda()

        # Un supervisor por dependencia: reconectan con backoff sin reiniciar el contenedor (T045).
        tareas = {
            asyncio.create_task(
                supervisar(
                    abrir_db,
                    sondear_db,
                    "postgres",
                    estado,
                    ajustes,
                    cerrar=Database.cerrar,
                    logger=_log,
                    registrar_listo=False,  # Database.conectar ya escribe su `result=listo`
                )
            ),
            asyncio.create_task(
                supervisar(
                    lambda: _abrir_sesion_kafka(ajustes, sesion),
                    _sondear_kafka,
                    "kafka",
                    estado,
                    ajustes,
                    cerrar=lambda consumidor: _cerrar_sesion_kafka(consumidor, sesion),
                    logger=_log,
                )
            ),
            asyncio.create_task(_consumir(ajustes, sesion, db, parada, indice)),
        }
        espera_parada = asyncio.create_task(parada.wait())
        try:
            await asyncio.wait(tareas | {espera_parada}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for tarea in tareas | {espera_parada}:
                tarea.cancel()
            resultados = await asyncio.gather(*tareas, espera_parada, return_exceptions=True)
        # Una tarea que termina por error (no por la parada) no debe dejar el servicio «sano» y mudo.
        for resultado in resultados:
            if isinstance(resultado, Exception):
                raise resultado
    finally:
        registrar(_log, "detenido", component="consumer")
        servidor.close()
        await db.cerrar()
