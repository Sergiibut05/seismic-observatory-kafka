"""Pruebas del formato de logs clave=valor (contracts/logs.md)."""

import io
import logging
import re

import pytest

from observatorio.common.logging import (
    RESULTADOS,
    FormateadorClaveValor,
    configurar_logging,
    registrar,
)

# Expresión regular de la sección «Comprobación (SC-009)».
PATRON = re.compile(r"^(\S+\s+\|\s+)?ts=\S+ level=\S+ service=(producer|consumer|api) result=\S+( .*)?$")
PATRON_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

SECRETO = "hunter2"


@pytest.fixture
def salida():
    return io.StringIO()


@pytest.fixture
def logger(salida):
    log = logging.getLogger(f"prueba.{id(salida)}")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorClaveValor("consumer", secretos=[SECRETO]))
    log.addHandler(manejador)
    return log


def lineas(salida):
    texto = salida.getvalue()
    return [l for l in texto.split("\n") if l != ""]


def campos(linea):
    """Descompone una línea en pares clave=valor respetando comillas."""
    resultado = {}
    for m in re.finditer(r'(\w+)=("(?:[^"\\]|\\.)*"|\S*)', linea):
        resultado[m.group(1)] = m.group(2)
    return resultado


def test_claves_obligatorias_y_orden(logger, salida):
    registrar(logger, "persistido", event_id="us7000abcd", updated=1767225600000, topic="eventos.live")
    (linea,) = lineas(salida)
    pares = campos(linea)
    assert list(pares)[:4] == ["ts", "level", "service", "result"]
    assert pares["level"] == "INFO"
    assert pares["service"] == "consumer"
    assert pares["result"] == "persistido"
    assert pares["event_id"] == "us7000abcd"
    assert pares["updated"] == "1767225600000"
    assert PATRON_TS.match(pares["ts"])
    assert PATRON.match(linea)


def test_ts_en_utc_con_milisegundos(logger, salida):
    registrar(logger, "info")
    pares = campos(lineas(salida)[0])
    assert PATRON_TS.match(pares["ts"])


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("sencillo", "sencillo"),
        ("con espacio", '"con espacio"'),
        ("a=b", '"a=b"'),
        ('con"comilla', '"con\\"comilla"'),
        ("barra\\inversa", '"barra\\\\inversa"'),
        ("dos\nlineas", '"dos\\nlineas"'),
        ("retorno\rcarro", '"retorno\\rcarro"'),
        ("", '""'),
    ],
)
def test_escape_de_valores(logger, salida, valor, esperado):
    registrar(logger, "info", motivo=valor)
    (linea,) = lineas(salida)
    assert campos(linea)["motivo"] == esperado
    assert PATRON.match(linea)


def test_un_valor_con_saltos_de_linea_nunca_produce_dos_lineas(logger, salida):
    registrar(logger, "error", reason="uno\ndos\r\ntres\ncuatro")
    assert len(lineas(salida)) == 1
    assert salida.getvalue().count("\n") == 1


def test_valores_none_y_numeros(logger, salida):
    registrar(logger, "rechazado", event_id=None, updated=None, offset=7, wait_s=2.0, activo=True)
    pares = campos(lineas(salida)[0])
    assert pares["event_id"] == "-"
    assert pares["updated"] == "-"
    assert pares["offset"] == "7"
    assert pares["wait_s"] == "2"
    assert pares["activo"] == "true"


def test_registrar_rechaza_result_fuera_del_conjunto(logger):
    with pytest.raises(ValueError):
        registrar(logger, "publicated")
    with pytest.raises(ValueError):
        registrar(logger, "published")


def test_conjunto_cerrado_de_results():
    assert set(RESULTADOS) == {
        "publicado",
        "persistido",
        "omitido",
        "rechazado",
        "error",
        "iniciado",
        "listo",
        "reintento",
        "detenido",
        "info",
    }


@pytest.mark.parametrize("resultado", sorted(RESULTADOS))
def test_cada_result_valido_cumple_el_patron(logger, salida, resultado):
    registrar(logger, resultado, component="x")
    assert PATRON.match(lineas(salida)[0])


@pytest.mark.parametrize(
    "nivel,esperado_nivel",
    [("DEBUG", "DEBUG"), ("INFO", "INFO"), ("WARNING", "WARNING"), ("ERROR", "ERROR")],
)
def test_niveles(logger, salida, nivel, esperado_nivel):
    registrar(logger, "info", nivel=nivel)
    assert campos(lineas(salida)[0])["level"] == esperado_nivel


def test_registro_de_libreria_sin_result_recibe_result_info(logger, salida):
    logger.info("Conectando con el broker")
    (linea,) = lineas(salida)
    pares = campos(linea)
    assert pares["result"] == "info"
    assert pares["msg"] == '"Conectando con el broker"'
    assert PATRON.match(linea)


def test_registro_de_libreria_de_nivel_error_recibe_result_error(logger, salida):
    logger.error("algo falló")
    logger.critical("muy mal")
    for linea in lineas(salida):
        assert campos(linea)["result"] == "error"
        assert PATRON.match(linea)


def test_registro_de_libreria_con_argumentos_y_saltos_de_linea(logger, salida):
    logger.warning("fallo %s\ncon detalle %d", "x", 3)
    (linea,) = lineas(salida)
    assert campos(linea)["msg"] == '"fallo x\\ncon detalle 3"'


def test_traceback_en_una_sola_linea(logger, salida):
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        registrar(logger, "error", reason="RuntimeError", exc_info=True)
    (linea,) = lineas(salida)
    pares = campos(linea)
    assert "exc" in pares
    assert pares["exc"].startswith('"')
    assert "Traceback" in pares["exc"]
    assert "RuntimeError: boom" in pares["exc"]
    assert PATRON.match(linea)


def test_traceback_de_registro_de_libreria(logger, salida):
    try:
        raise ValueError("fallo de libreria")
    except ValueError:
        logger.exception("capturado")
    (linea,) = lineas(salida)
    pares = campos(linea)
    assert pares["result"] == "error"
    assert "ValueError: fallo de libreria" in pares["exc"]


def test_secreto_conocido_se_sustituye(logger, salida):
    registrar(logger, "error", reason=f"fallo con {SECRETO} en medio", otro=SECRETO)
    logger.info("mensaje con %s", SECRETO)
    texto = salida.getvalue()
    assert SECRETO not in texto
    assert "***" in texto


def test_secreto_en_el_traceback_se_sustituye(logger, salida):
    try:
        raise RuntimeError(f"clave={SECRETO}")
    except RuntimeError:
        registrar(logger, "error", exc_info=True)
    assert SECRETO not in salida.getvalue()


def test_configurar_logging_instala_el_formateador(capsys):
    raiz = logging.getLogger()
    anteriores = list(raiz.handlers)
    nivel_previo = raiz.level
    try:
        configurar_logging("api", "INFO", secretos=[SECRETO])
        logging.getLogger("aiokafka.conn").warning("de una librería con %s", SECRETO)
        registrar(logging.getLogger("observatorio.prueba"), "iniciado")
        salida = capsys.readouterr().out
        ls = [l for l in salida.split("\n") if l]
        assert len(ls) == 2
        for linea in ls:
            assert PATRON.match(linea), linea
            assert "service=api" in linea
        assert SECRETO not in salida
    finally:
        raiz.handlers[:] = anteriores
        raiz.setLevel(nivel_previo)


def test_configurar_logging_respeta_el_nivel(capsys):
    raiz = logging.getLogger()
    anteriores = list(raiz.handlers)
    nivel_previo = raiz.level
    try:
        configurar_logging("producer", "WARNING")
        registrar(logging.getLogger("observatorio.prueba"), "info", nivel="INFO")
        registrar(logging.getLogger("observatorio.prueba"), "error", nivel="ERROR")
        ls = [l for l in capsys.readouterr().out.split("\n") if l]
        assert len(ls) == 1
        assert "level=ERROR" in ls[0]
    finally:
        raiz.handlers[:] = anteriores
        raiz.setLevel(nivel_previo)
