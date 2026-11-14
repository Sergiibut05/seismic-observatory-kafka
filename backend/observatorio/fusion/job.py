"""Trabajo de PySpark Structured Streaming: topics por fuente → fusión → `eventos.live`.

Qué hace Spark (research.md de 013, «Qué hace Spark y qué hace Python»):
- Lee `eventos.usgs` y `eventos.emsc` con sus offsets en el *checkpoint*, en micro-lotes con tope
  de tamaño (`maxOffsetsPerTrigger`).
- Con Spark SQL saca el id y la versión de cada mensaje y se queda con la última versión de cada
  informe del lote (una ventana por `(topic, id)`).
- Escribe los eventos fusionados en `eventos.live` con su conector de Kafka.

Qué hace Python (en el driver, dentro de `foreachBatch`): normalizar y emparejar con el estado
de PostgreSQL. Orden por lote: decidir → escribir en Kafka → confirmar el estado → offset.
"""

import glob
import logging
import os

from observatorio.common.config import AjustesFusion
from observatorio.common.logging import registrar
from observatorio.fusion import estado as estado_bd
from observatorio.fusion.emparejar import fusionar
from observatorio.fusion.normalizar import Descarte, Informe, normalizar

_log = logging.getLogger("observatorio.fusion")


def crear_sesion(ajustes: AjustesFusion):
    from pyspark.sql import SparkSession

    # Los jars del conector de Kafka se descargan al construir la imagen: el arranque no baja nada.
    jars = sorted(glob.glob(os.path.join(ajustes.jars_dir, "*.jar")))
    constructor = (
        SparkSession.builder.appName("observatorio-fusion")
        .master(ajustes.spark_master)
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.session.timeZone", "UTC")
    )
    if jars:
        constructor = constructor.config("spark.jars", ",".join(jars))
    sesion = constructor.getOrCreate()
    sesion.sparkContext.setLogLevel("WARN")
    return sesion


def ultimas_versiones(lote):
    """Una fila por informe: la de versión más alta (y, a igualdad, la de offset más alto).

    USGS da la versión en ms (`updated`, 13 cifras) y EMSC en ISO (`lastupdate`): dentro de una
    misma fuente las dos se ordenan bien como texto. Un mensaje ilegible (sin id) va solo, para
    que la fusión lo descarte con su motivo.
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    texto = F.col("value").cast("string")
    con_id = (
        lote.withColumn("id_fuente", F.get_json_object(texto, "$.event.id"))
        .withColumn(
            "version",
            F.coalesce(
                F.get_json_object(texto, "$.event.properties.updated"),
                F.get_json_object(texto, "$.event.properties.lastupdate"),
            ),
        )
        .withColumn(
            "grupo",
            F.coalesce(F.col("id_fuente"), F.concat_ws(":", F.col("partition").cast("string"), F.col("offset").cast("string"))),
        )
    )
    ventana = Window.partitionBy("topic", "grupo").orderBy(F.col("version").desc_nulls_last(), F.col("offset").desc())
    return (
        con_id.withColumn("n", F.row_number().over(ventana))
        .filter(F.col("n") == 1)
        .select("topic", "partition", "offset", "key", "value")
    )


def procesar_lote(sesion, ajustes: AjustesFusion, estado: estado_bd.EstadoFusion, lote, lote_id: int) -> dict:
    """`foreachBatch`: decide con el estado, escribe en Kafka y solo entonces confirma."""
    recibidos = lote.count()
    if recibidos == 0:
        return {}
    filas = ultimas_versiones(lote).collect()

    informes: list[Informe] = []
    descartes: list[tuple[Descarte, str, int, int]] = []
    for fila in filas:
        clave = bytes(fila["key"]) if fila["key"] is not None else None
        valor = bytes(fila["value"]) if fila["value"] is not None else None
        resultado = normalizar(clave, valor, fila["topic"])
        if isinstance(resultado, Informe):
            informes.append(resultado)
        else:
            descartes.append((resultado, fila["topic"], fila["partition"], fila["offset"]))

    with estado.lote() as conn:
        guardados, canonicos = estado_bd.cargar(conn, informes)
        resultado = fusionar(informes, guardados, canonicos)
        if resultado.mensajes:
            salida = sesion.createDataFrame(list(resultado.mensajes), "key binary, value binary")
            (
                salida.write.format("kafka")
                .option("kafka.bootstrap.servers", ajustes.kafka_bootstrap_servers)
                .option("topic", ajustes.topic_live)
                .option("kafka.acks", "all")
                .option("kafka.enable.idempotence", "true")
                .save()
            )
        # Kafka ya tiene los mensajes: ahora se guarda el estado (al salir del `with`, COMMIT).
        estado_bd.guardar(conn, resultado)
        estado_bd.descartar(conn, descartes)

    resumen = dict(resultado.resumen)
    resumen.update(recibidos=recibidos, duplicados_en_lote=recibidos - len(filas), descartes=len(descartes))
    registrar(_log, "listo", component="fusion", action="lote", lote=lote_id, **resumen)
    for descarte, topic, particion, offset in descartes:
        registrar(
            _log,
            "rechazado",
            nivel="WARNING",
            component="fusion",
            motivo=descarte.motivo,
            source=descarte.fuente,
            event_id=descarte.id_origen,
            topic=topic,
            partition=particion,
            offset=offset,
        )
    return resumen


def iniciar_consulta(sesion, ajustes: AjustesFusion, estado: estado_bd.EstadoFusion):
    lectura = (
        sesion.readStream.format("kafka")
        .option("kafka.bootstrap.servers", ajustes.kafka_bootstrap_servers)
        .option("subscribePattern", ajustes.patron_fuentes)
        .option("startingOffsets", "earliest")
        .option("maxOffsetsPerTrigger", str(ajustes.max_por_lote))
        .option("failOnDataLoss", "false")
        # Descubre pronto un topic que se crea después de arrancar (por defecto, cada 5 min).
        .option("kafka.metadata.max.age.ms", "10000")
        .load()
        .select("topic", "partition", "offset", "key", "value")
    )
    return (
        lectura.writeStream.queryName("fusion")
        .foreachBatch(lambda lote, lote_id: procesar_lote(sesion, ajustes, estado, lote, lote_id))
        .option("checkpointLocation", ajustes.checkpoint_dir)
        .trigger(processingTime=f"{ajustes.trigger_segundos} seconds")
        .start()
    )
