"""Pruebas de la creación del topic (sin broker). R-04, R-05."""

import asyncio
import io
import logging
from types import SimpleNamespace

import pytest

from observatorio.common.kafka import (
    ErrorCreacionTopic,
    ErrorReconciliacionTopic,
    configuracion_topic,
    ensure_topic,
    interpretar_creacion,
    plan_reconciliacion,
    sonda_kafka,
    topic_listado,
    wait_for_topic,
)
from observatorio.common.logging import FormateadorClaveValor
from observatorio.common.retry import Backoff


# --- configuración --------------------------------------------------------


def test_configuracion_con_retencion_de_siete_dias():
    assert configuracion_topic(604_800_000) == {"retention.ms": "604800000", "segment.ms": "86400000"}


def test_configuracion_con_retencion_corta_acota_el_segmento():
    assert configuracion_topic(3_600_000) == {"retention.ms": "3600000", "segment.ms": "3600000"}


def test_configuracion_en_el_limite_de_un_dia():
    assert configuracion_topic(86_400_000)["segment.ms"] == "86400000"
    assert configuracion_topic(86_400_001)["segment.ms"] == "86400000"


def test_los_valores_van_como_texto():
    assert all(isinstance(v, str) for v in configuracion_topic(1000).values())


# --- interpretación de la respuesta de create_topics ----------------------


def respuesta(codigo, mensaje=None, topic="eventos.live"):
    return SimpleNamespace(topic_errors=[(topic, codigo, mensaje)])


def test_codigo_0_es_creado():
    assert interpretar_creacion(respuesta(0), "eventos.live") == "creado"


def test_codigo_36_es_ya_existe_sin_excepcion():
    assert interpretar_creacion(respuesta(36, "Topic already exists"), "eventos.live") == "existe"


@pytest.mark.parametrize("codigo", [7, 8, 37, 41, 87])
def test_otro_codigo_es_un_error(codigo):
    with pytest.raises(ErrorCreacionTopic) as exc:
        interpretar_creacion(respuesta(codigo, "fallo"), "eventos.live")
    assert str(codigo) in str(exc.value)


def test_respuesta_sin_el_topic_es_un_error():
    with pytest.raises(ErrorCreacionTopic):
        interpretar_creacion(SimpleNamespace(topic_errors=[("otro", 0, None)]), "eventos.live")


def test_respuesta_vacia_es_un_error():
    with pytest.raises(ErrorCreacionTopic):
        interpretar_creacion(SimpleNamespace(topic_errors=[]), "eventos.live")


# --- topic_listado --------------------------------------------------------


def test_topic_listado():
    assert topic_listado(["a", "eventos.live", "b"], "eventos.live")
    assert not topic_listado(["a", "b"], "eventos.live")
    assert not topic_listado([], "eventos.live")


# --- ensure_topic con un cliente falso ------------------------------------


@pytest.fixture
def salida():
    return io.StringIO()


@pytest.fixture
def logger(salida):
    log = logging.getLogger(f"prueba.kafka.{id(salida)}")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorClaveValor("producer"))
    log.addHandler(manejador)
    return log


def respuesta_describe(retention, segment, error=0, extra=True):
    entradas = [
        ("retention.ms", str(retention), False, 1, False, []),
        ("segment.ms", str(segment), False, 1, False, []),
    ]
    if extra:
        entradas.append(("cleanup.policy", "delete", False, 5, False, []))
    return SimpleNamespace(resources=[(error, "", 2, "eventos.live", entradas)])


def respuesta_alter(error=0):
    return [SimpleNamespace(resources=[(error, "", 2, "eventos.live")])]


class AdminFalso:
    def __init__(
        self,
        respuestas=None,
        topics=None,
        describe=None,
        particiones=3,
        alter=None,
    ):
        self.creaciones = []
        self._respuestas = list(respuestas or [])
        self._topics = list(topics or [])
        self.listados = 0
        self._describe = describe
        self._particiones = particiones
        self._alter = alter if alter is not None else respuesta_alter()
        self.descripciones = []
        self.alteraciones = []

    async def describe_configs(self, recursos, **kw):
        self.descripciones.append(recursos)
        return [self._describe]

    async def describe_topics(self, topics=None):
        return [{"topic": topics[0], "error_code": 0, "partitions": [{}] * self._particiones}]

    async def alter_configs(self, recursos):
        self.alteraciones.append(recursos)
        return self._alter

    async def create_topics(self, nuevos, **kw):
        self.creaciones.extend(nuevos)
        return self._respuestas.pop(0)

    async def list_topics(self):
        self.listados += 1
        return self._topics.pop(0) if len(self._topics) > 1 else self._topics[0]


def test_ensure_topic_crea_con_retencion_y_segmento(logger, salida):
    admin = AdminFalso([respuesta(0)])
    accion = asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger))
    assert accion == "creado"
    (nuevo,) = admin.creaciones
    assert nuevo.name == "eventos.live"
    assert nuevo.num_partitions == 3
    assert nuevo.replication_factor == 1
    assert nuevo.topic_configs == {"retention.ms": "604800000", "segment.ms": "86400000"}
    linea = salida.getvalue()
    assert "result=listo" in linea
    assert "component=topic" in linea
    assert "action=topic_creado" in linea


def test_ensure_topic_existente_y_conforme_no_altera(logger, salida):
    admin = AdminFalso([respuesta(36)], describe=respuesta_describe(604_800_000, 86_400_000))
    assert asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger)) == "conforme"
    assert admin.alteraciones == []
    linea = salida.getvalue()
    assert "result=listo component=topic action=topic_conforme" in linea
    assert "retention_ms=604800000" in linea and "partitions=3" in linea


def test_ensure_topic_existente_con_otra_retencion_reconcilia(logger, salida):
    admin = AdminFalso([respuesta(36)], describe=respuesta_describe(604_800_000, 86_400_000))
    assert asyncio.run(ensure_topic(admin, "eventos.live", 3, 3_600_000, logger=logger)) == "reconciliado"
    (recursos,) = admin.alteraciones
    (recurso,) = recursos
    assert recurso.name == "eventos.live"
    # alter_configs es no incremental: se envían SIEMPRE las dos claves (R-05)
    assert recurso.configs == {"retention.ms": "3600000", "segment.ms": "3600000"}
    linea = salida.getvalue()
    assert "action=topic_reconciliado" in linea
    assert "retention_ms=3600000" in linea
    assert "topic_conforme" not in linea


def test_reconciliar_solo_el_segmento_tambien_envia_ambas_claves(logger):
    admin = AdminFalso([respuesta(36)], describe=respuesta_describe(604_800_000, 604_800_000))
    asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger))
    ((recurso,),) = admin.alteraciones
    assert recurso.configs == {"retention.ms": "604800000", "segment.ms": "86400000"}


def test_topic_recien_creado_no_se_describe_ni_se_altera(logger):
    admin = AdminFalso([respuesta(0)])
    asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger))
    assert admin.descripciones == [] and admin.alteraciones == []


def test_particiones_distintas_se_avisan_sin_modificarlas(logger, salida):
    admin = AdminFalso([respuesta(36)], describe=respuesta_describe(604_800_000, 86_400_000), particiones=1)
    resultado = asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger))
    assert resultado == "conforme"
    assert admin.alteraciones == []
    assert admin.creaciones[0].num_partitions == 3  # solo el intento inicial de creación
    linea = [l for l in salida.getvalue().split("\n") if "particiones_distintas" in l][0]
    assert "level=WARNING" in linea
    assert "partitions_actuales=1" in linea and "partitions_configuradas=3" in linea
    # La línea de resultado informa de las particiones reales, no de las configuradas.
    assert "action=topic_conforme topic=eventos.live partitions=1 " in salida.getvalue()


def test_un_error_al_alterar_se_propaga(logger):
    admin = AdminFalso(
        [respuesta(36)],
        describe=respuesta_describe(604_800_000, 86_400_000),
        alter=respuesta_alter(error=41),
    )
    with pytest.raises(ErrorReconciliacionTopic):
        asyncio.run(ensure_topic(admin, "eventos.live", 3, 3_600_000, logger=logger))


def test_un_error_al_describir_se_propaga(logger):
    admin = AdminFalso([respuesta(36)], describe=respuesta_describe(1, 1, error=3))
    with pytest.raises(ErrorReconciliacionTopic):
        asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger))


def test_no_se_verifica_con_describe_justo_despues_de_alterar(logger):
    admin = AdminFalso([respuesta(36)], describe=respuesta_describe(604_800_000, 86_400_000))
    asyncio.run(ensure_topic(admin, "eventos.live", 3, 3_600_000, logger=logger))
    assert len(admin.descripciones) == 1  # solo la lectura previa (desfase medido en R-05)


# --- plan de reconciliación (puro) ----------------------------------------

DESEADO_7D = {"retention.ms": "604800000", "segment.ms": "86400000"}


def test_plan_sin_cambios_si_coinciden():
    plan = plan_reconciliacion(dict(DESEADO_7D), DESEADO_7D)
    assert plan.accion == "sin_cambios"
    assert plan.cambios == {}
    assert plan.avisos == ()


def test_plan_ignora_otras_claves_del_topic():
    actual = {**DESEADO_7D, "cleanup.policy": "delete", "max.message.bytes": "1048588"}
    assert plan_reconciliacion(actual, DESEADO_7D).accion == "sin_cambios"


def test_plan_altera_solo_la_retencion_si_difiere():
    actual = {"retention.ms": "3600000", "segment.ms": "86400000"}
    plan = plan_reconciliacion(actual, DESEADO_7D)
    assert plan.accion == "alterar"
    assert plan.cambios == {"retention.ms": "604800000"}


def test_plan_altera_solo_el_segmento_si_difiere():
    actual = {"retention.ms": "604800000", "segment.ms": "604800000"}
    plan = plan_reconciliacion(actual, DESEADO_7D)
    assert plan.accion == "alterar"
    assert plan.cambios == {"segment.ms": "86400000"}


def test_plan_altera_ambas_si_difieren():
    plan = plan_reconciliacion({"retention.ms": "1", "segment.ms": "2"}, DESEADO_7D)
    assert plan.cambios == DESEADO_7D


def test_plan_trata_la_clave_ausente_como_diferencia():
    plan = plan_reconciliacion({"retention.ms": "604800000"}, DESEADO_7D)
    assert plan.accion == "alterar"
    assert plan.cambios == {"segment.ms": "86400000"}


def test_plan_compara_como_texto_aunque_llegue_un_entero():
    assert plan_reconciliacion({"retention.ms": 604800000, "segment.ms": 86400000}, DESEADO_7D).accion == "sin_cambios"


def test_plan_avisa_si_las_particiones_difieren_sin_proponer_cambiarlas():
    plan = plan_reconciliacion(dict(DESEADO_7D), DESEADO_7D, particiones_actuales=1, particiones_deseadas=3)
    assert plan.accion == "sin_cambios"
    assert plan.avisos == ("particiones_distintas",)
    assert "partitions" not in plan.cambios and "num.partitions" not in plan.cambios


def test_plan_no_avisa_si_las_particiones_coinciden_o_se_desconocen():
    assert plan_reconciliacion(dict(DESEADO_7D), DESEADO_7D, 3, 3).avisos == ()
    assert plan_reconciliacion(dict(DESEADO_7D), DESEADO_7D).avisos == ()


def test_plan_con_cambios_y_particiones_distintas_hace_ambas_cosas():
    plan = plan_reconciliacion({"retention.ms": "1", "segment.ms": "1"}, DESEADO_7D, 1, 3)
    assert plan.accion == "alterar"
    assert plan.avisos == ("particiones_distintas",)


def test_ensure_topic_propaga_otros_errores(logger):
    admin = AdminFalso([respuesta(41, "no es controlador")])
    with pytest.raises(ErrorCreacionTopic):
        asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger))


# --- wait_for_topic -------------------------------------------------------


class Reloj:
    def __init__(self):
        self.esperas = []

    async def sleep(self, s):
        self.esperas.append(s)


def test_wait_for_topic_reintenta_hasta_que_aparece(logger, salida):
    admin = AdminFalso(topics=[[], ["__consumer_offsets"], ["eventos.live"]])
    reloj = Reloj()
    asyncio.run(wait_for_topic(admin, "eventos.live", Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger))
    assert reloj.esperas == [1, 2]
    texto = salida.getvalue()
    assert texto.count("result=reintento") == 2
    assert "reason=topic_no_existe" in texto


def test_wait_for_topic_no_espera_si_ya_existe(logger, salida):
    admin = AdminFalso(topics=[["eventos.live"]])
    reloj = Reloj()
    asyncio.run(wait_for_topic(admin, "eventos.live", Backoff(1, 2, 30), sleep=reloj.sleep, logger=logger))
    assert reloj.esperas == []
    assert salida.getvalue() == ""


# --- sonda_kafka ----------------------------------------------------------


def test_sonda_devuelve_el_resultado():
    async def metadatos():
        return "ok"

    assert asyncio.run(sonda_kafka(metadatos, timeout=1)) == "ok"


def test_sonda_agota_el_tiempo():
    async def colgado():
        await asyncio.sleep(10)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(sonda_kafka(colgado, timeout=0.05))


def test_sonda_propaga_el_fallo():
    async def falla():
        raise ConnectionError("sin broker")

    with pytest.raises(ConnectionError):
        asyncio.run(sonda_kafka(falla, timeout=1))
