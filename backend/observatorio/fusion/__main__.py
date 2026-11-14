"""Servicio de fusión: `python -m observatorio.fusion`.

1. Conecta con PostgreSQL (con espera creciente), crea el esquema `fusion` y siembra los eventos
   previos.
2. Arranca la consulta de Spark y un latido para el healthcheck.
3. Si la consulta falla (Kafka o PostgreSQL caídos a mitad de un lote), sale con error: Compose
   reinicia el servicio y Spark continúa desde el *checkpoint*, repitiendo el lote que no terminó.
"""

import logging
import signal
import sys
import threading

from observatorio.common.config import ajustes_fusion, cargar_o_salir
from observatorio.common.logging import configurar_logging, registrar
from observatorio.fusion.estado import EstadoFusion
from observatorio.fusion.job import crear_sesion, iniciar_consulta
from observatorio.fusion.salud import latir_mientras

_log = logging.getLogger("observatorio.fusion")


def main() -> int:
    ajustes = cargar_o_salir("fusion", ajustes_fusion)
    configurar_logging("fusion", ajustes.log_level, ajustes.secretos())
    # py4j (el puente Python ↔ JVM de PySpark) anota cada orden interna a nivel INFO: es ruido.
    logging.getLogger("py4j").setLevel(logging.WARNING)
    registrar(_log, "iniciado", component="fusion", patron=ajustes.patron_fuentes, salida=ajustes.topic_live)

    estado = EstadoFusion(ajustes.postgres, ajustes.backoff)
    estado.conectar()
    sembrados = estado.asegurar()
    registrar(_log, "listo", component="fusion", action="esquema", sembrados=sembrados["informes"])

    sesion = crear_sesion(ajustes)
    consulta = iniciar_consulta(sesion, ajustes, estado)
    parada = threading.Event()
    latir_mientras(lambda: consulta.isActive, parada)

    def parar(*_):
        registrar(_log, "detenido", component="fusion", reason="señal")
        parada.set()
        consulta.stop()

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    codigo = 0
    try:
        consulta.awaitTermination()
        if not parada.is_set():
            codigo = 1  # la consulta acabó sin que nadie la parara
    except Exception as exc:  # StreamingQueryException: el lote falló; Compose reinicia
        registrar(_log, "error", nivel="ERROR", component="fusion", reason=type(exc).__name__, detalle=str(exc)[:500])
        codigo = 1
    finally:
        parada.set()
        estado.cerrar()
        sesion.stop()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
