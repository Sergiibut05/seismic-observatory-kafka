"""Descarga el conector de Kafka de Spark y sus dependencias (se ejecuta al construir la imagen).

Spark resuelve `spark.jars.packages` desde Maven Central con Ivy. Se hace una vez en el *build*
y se copian los jars a `SPARK_JARS_DIR`; en ejecución, `job.crear_sesion` los pasa con `spark.jars`.
"""

import glob
import os
import shutil

from pyspark.sql import SparkSession

PAQUETE = "org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.1"
IVY = "/tmp/ivy"
DESTINO = os.environ.get("SPARK_JARS_DIR", "/opt/spark-jars")


def main() -> None:
    sesion = (
        SparkSession.builder.master("local[1]")
        .config("spark.jars.packages", PAQUETE)
        .config("spark.jars.ivy", IVY)
        .getOrCreate()
    )
    sesion.stop()
    os.makedirs(DESTINO, exist_ok=True)
    jars = glob.glob(os.path.join(IVY, "jars", "*.jar"))
    if not any("spark-sql-kafka" in os.path.basename(j) for j in jars):
        raise SystemExit("no se descargó el conector de Kafka")
    for jar in jars:
        shutil.copy(jar, DESTINO)
    shutil.rmtree(IVY, ignore_errors=True)
    print("jars:", ", ".join(sorted(os.listdir(DESTINO))))


if __name__ == "__main__":
    main()
