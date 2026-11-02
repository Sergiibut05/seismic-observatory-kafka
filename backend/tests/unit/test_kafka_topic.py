"""Pruebas de la creación del topic (sin broker). R-04, R-05."""

import asyncio
import io
import logging
from types import SimpleNamespace

import pytest

from observatorio.common.kafka import (
    ErrorCreacionTopic,
    configuracion_topic,
    ensure_topic,
    interpretar_creacion,
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


class AdminFalso:
    def __init__(self, respuestas=None, topics=None):
        self.creaciones = []
        self._respuestas = list(respuestas or [])
        self._topics = list(topics or [])
        self.listados = 0

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


def test_ensure_topic_existente_no_lanza(logger, salida):
    admin = AdminFalso([respuesta(36)])
    assert asyncio.run(ensure_topic(admin, "eventos.live", 3, 604_800_000, logger=logger)) == "existe"
    assert "action=topic_existente" in salida.getvalue()


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
