"""Pruebas del contrato Kafka v1 (contracts/mensaje-kafka-v1.md)."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from observatorio.common.contrato import (
    MODOS,
    PREFIJO_SINTETICO,
    SCHEMA_VERSION,
    MensajeValido,
    Rechazo,
    construir_mensaje,
    es_sintetico,
    ms_a_datetime,
    validar_mensaje,
)

EJEMPLO = Path(__file__).resolve().parent.parent / "fixtures" / "mensaje_v1_ejemplo.json"


def base():
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


def serializar(mensaje) -> bytes:
    return json.dumps(mensaje, ensure_ascii=False).encode("utf-8")


def validar(mensaje, clave=b"synthetic-smoke-0001", modo="live"):
    valor = mensaje if isinstance(mensaje, (bytes, type(None))) else serializar(mensaje)
    return validar_mensaje(clave, valor, modo)


def motivo(resultado):
    assert isinstance(resultado, Rechazo), resultado
    return resultado.motivo


def con(**cambios):
    m = base()
    m.update(cambios)
    return m


def sin(campo):
    m = base()
    del m[campo]
    return m


def con_evento(mutador):
    m = base()
    mutador(m["event"])
    return m


# --- el ejemplo es válido -------------------------------------------------


def test_constantes():
    assert SCHEMA_VERSION == 1
    assert set(MODOS) == {"live", "replay"}
    assert PREFIJO_SINTETICO == "synthetic-"


def test_el_ejemplo_es_valido():
    resultado = validar(base())
    assert isinstance(resultado, MensajeValido)
    assert resultado.event_id == "synthetic-smoke-0001"
    assert resultado.updated_ms == 1767225600000
    assert resultado.updated == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert resultado.source == "synthetic-smoke"
    assert resultado.mode == "live"
    assert resultado.sintetico is True
    assert resultado.ingested_at == datetime(2026, 11, 2, 12, 0, 0, 123000, tzinfo=timezone.utc)
    assert resultado.mensaje == base()


def test_mensaje_real_no_es_sintetico():
    m = base()
    m["source"] = "usgs"
    m["event"]["id"] = "us7000abcd"
    resultado = validar(m, clave=b"us7000abcd")
    assert isinstance(resultado, MensajeValido)
    assert resultado.sintetico is False


def test_modo_replay_en_topic_replay_es_valido():
    resultado = validar(con(mode="replay"), modo="replay")
    assert isinstance(resultado, MensajeValido)
    assert resultado.mode == "replay"


def test_ingested_at_con_mas_decimales_o_con_desplazamiento_cero():
    for texto in ("2026-11-02T12:00:00Z", "2026-11-02T12:00:00.123456Z", "2026-11-02T12:00:00.1+00:00"):
        assert isinstance(validar(con(ingested_at=texto)), MensajeValido), texto


# --- un caso por motivo de rechazo ----------------------------------------


def test_valor_ausente():
    assert motivo(validar_mensaje(b"k", None, "live")) == "valor_ausente"


@pytest.mark.parametrize(
    "valor",
    [
        b"{esto no es json",
        b"",
        b"\xff\xfe\x80no utf8",
        b'{"a": NaN}',
        b'{"a": Infinity}',
        b'{"a": -Infinity}',
    ],
)
def test_json_ilegible(valor):
    assert motivo(validar_mensaje(b"k", valor, "live")) == "json_ilegible"


@pytest.mark.parametrize("valor", [b"[]", b'"texto"', b"42", b"null", b"true"])
def test_no_es_objeto(valor):
    assert motivo(validar_mensaje(b"k", valor, "live")) == "no_es_objeto"


@pytest.mark.parametrize("campo", ["schema_version", "source", "ingested_at", "mode", "event"])
def test_campo_ausente(campo):
    resultado = validar(sin(campo))
    assert motivo(resultado) == "campo_ausente"
    assert campo in resultado.detalle


def test_campo_desconocido_en_la_raiz():
    resultado = validar(con(extra=1))
    assert motivo(resultado) == "campo_ausente"
    assert "extra" in resultado.detalle


@pytest.mark.parametrize("version", ["1", True, 2, 0, 1.0, None, [1]])
def test_schema_version_no_soportada(version):
    assert motivo(validar(con(schema_version=version))) == "schema_version_no_soportada"


@pytest.mark.parametrize("valor", ["USGS", "1abc", "", "con espacio", "a" * 64, "ñandú"])
def test_source_invalido(valor):
    assert motivo(validar(con(source=valor))) == "source_invalido"


@pytest.mark.parametrize("valor", [5, None, ["usgs"]])
def test_source_con_tipo_invalido(valor):
    assert motivo(validar(con(source=valor))) == "tipo_invalido"


@pytest.mark.parametrize("valor", ["LIVE", "historico", ""])
def test_mode_invalido(valor):
    assert motivo(validar(con(mode=valor))) == "mode_invalido"


def test_mode_con_tipo_invalido():
    assert motivo(validar(con(mode=1))) == "tipo_invalido"


def test_mode_replay_en_el_topic_live():
    assert motivo(validar(con(mode="replay"), modo="live")) == "mode_no_corresponde_al_topic"


def test_mode_live_en_el_topic_replay():
    assert motivo(validar(con(mode="live"), modo="replay")) == "mode_no_corresponde_al_topic"


@pytest.mark.parametrize(
    "texto",
    ["2026-11-02T12:00:00", "2026-11-02T12:00:00+01:00", "2026-11-02", "ayer", "", "2026-13-45T00:00:00Z"],
)
def test_ingested_at_invalido(texto):
    assert motivo(validar(con(ingested_at=texto))) == "ingested_at_invalido"


def test_ingested_at_con_tipo_invalido():
    assert motivo(validar(con(ingested_at=1767225600))) == "tipo_invalido"


@pytest.mark.parametrize("evento", ["texto", [], None, 5])
def test_event_con_tipo_invalido(evento):
    assert motivo(validar(con(event=evento))) == "tipo_invalido"


@pytest.mark.parametrize("valor", [None, "", 5, ["x"]])
def test_evento_sin_id(valor):
    m = con_evento(lambda e: e.__setitem__("id", valor))
    assert motivo(validar(m, clave=b"x")) == "evento_sin_id"


def test_evento_sin_la_clave_id():
    m = con_evento(lambda e: e.pop("id"))
    assert motivo(validar(m)) == "evento_sin_id"


def test_clave_ausente():
    assert motivo(validar(base(), clave=None)) == "clave_ausente"


@pytest.mark.parametrize("clave", [b"otra", b"", b"synthetic-smoke-0001 ", b"\xff\xfe"])
def test_clave_distinta_de_id(clave):
    assert motivo(validar(base(), clave=clave)) == "clave_distinta_de_id"


@pytest.mark.parametrize("valor", [True, False, 1.5, "1", -1, 4102444800001, None, [1]])
def test_updated_invalido(valor):
    m = con_evento(lambda e: e["properties"].__setitem__("updated", valor))
    assert motivo(validar(m)) == "updated_invalido"


def test_updated_ausente_o_properties_ausente():
    assert motivo(validar(con_evento(lambda e: e["properties"].pop("updated")))) == "updated_invalido"
    assert motivo(validar(con_evento(lambda e: e.pop("properties")))) == "updated_invalido"
    assert motivo(validar(con_evento(lambda e: e.__setitem__("properties", "x")))) == "updated_invalido"


@pytest.mark.parametrize("ms", [0, 4102444800000])
def test_updated_en_los_limites_es_valido(ms):
    m = con_evento(lambda e: e["properties"].__setitem__("updated", ms))
    resultado = validar(m)
    assert isinstance(resultado, MensajeValido)
    assert resultado.updated_ms == ms


def test_sintetico_inconsistente_source_sintetico_e_id_real():
    m = con_evento(lambda e: e.__setitem__("id", "us7000abcd"))
    assert motivo(validar(m, clave=b"us7000abcd")) == "sintetico_inconsistente"


def test_sintetico_inconsistente_source_real_e_id_sintetico():
    assert motivo(validar(con(source="usgs"))) == "sintetico_inconsistente"


# --- orden de comprobación ------------------------------------------------


def test_el_primer_fallo_decide_el_motivo():
    # schema_version, source y mode son inválidos a la vez: manda schema_version.
    m = con(schema_version=2, source="MAL", mode="x")
    assert motivo(validar(m)) == "schema_version_no_soportada"
    # source antes que mode
    assert motivo(validar(con(source="MAL", mode="x"))) == "source_invalido"
    # mode (valor) antes que mode frente al topic y que ingested_at
    assert motivo(validar(con(mode="x", ingested_at="mal"))) == "mode_invalido"
    # mode frente al topic antes que ingested_at
    assert motivo(validar(con(mode="replay", ingested_at="mal"))) == "mode_no_corresponde_al_topic"
    # ingested_at antes que event
    assert motivo(validar(con(ingested_at="mal", event="x"))) == "ingested_at_invalido"


def test_id_antes_que_clave_y_clave_antes_que_updated():
    m = con_evento(lambda e: (e.__setitem__("id", ""), e["properties"].__setitem__("updated", True)))
    assert motivo(validar(m, clave=None)) == "evento_sin_id"
    assert motivo(validar(base(), clave=None)) == "clave_ausente"
    m2 = con_evento(lambda e: e["properties"].__setitem__("updated", True))
    assert motivo(validar(m2, clave=b"otra")) == "clave_distinta_de_id"
    assert motivo(validar(m2)) == "updated_invalido"


def test_updated_antes_que_coherencia_sintetica():
    m = con(source="usgs")
    m["event"]["properties"]["updated"] = "x"
    assert motivo(validar(m)) == "updated_invalido"


def test_campos_de_raiz_antes_que_schema_version():
    m = base()
    m["schema_version"] = 2
    m["extra"] = 1
    assert motivo(validar(m)) == "campo_ausente"


# --- el rechazo identifica el evento cuando se conoce ----------------------


def test_rechazo_incluye_event_id_y_updated_si_se_conocen():
    resultado = validar(base(), clave=b"otra")
    assert resultado.event_id == "synthetic-smoke-0001"
    assert resultado.updated == 1767225600000


def test_rechazo_sin_datos_conocidos():
    resultado = validar_mensaje(b"k", b"{roto", "live")
    assert resultado.event_id is None
    assert resultado.updated is None


# --- conversión de tiempos ------------------------------------------------


def test_updated_ms_a_datetime_utc_exacto():
    assert ms_a_datetime(1767225600000) == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert ms_a_datetime(1767225600123) == datetime(2026, 1, 1, 0, 0, 0, 123000, tzinfo=timezone.utc)
    assert ms_a_datetime(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_conversion_sin_float():
    # 2**53 + 1 ms no es representable en un float; la aritmética entera lo conserva.
    ms = 4102444800000
    assert ms_a_datetime(ms).utcoffset() == timedelta(0)
    assert ms_a_datetime(ms + 1) - ms_a_datetime(ms) == timedelta(milliseconds=1)
    assert ms_a_datetime(1767225600999).microsecond == 999000


# --- sintético ------------------------------------------------------------


def test_es_sintetico():
    assert es_sintetico("synthetic-smoke") is True
    assert es_sintetico("synthetic-smoke-0001") is True
    assert es_sintetico("usgs") is False
    assert es_sintetico("us7000abcd") is False
    assert es_sintetico("Synthetic-x") is False


# --- construir_mensaje ----------------------------------------------------


def test_construir_mensaje_y_validarlo():
    evento = base()["event"]
    original = copy.deepcopy(evento)
    ingesta = datetime(2026, 11, 2, 12, 0, 0, 123456, tzinfo=timezone.utc)
    clave, valor = construir_mensaje(evento, "synthetic-smoke", "live", ingesta)
    assert isinstance(clave, bytes) and isinstance(valor, bytes)
    assert clave == b"synthetic-smoke-0001"
    cuerpo = json.loads(valor.decode("utf-8"))
    assert cuerpo["schema_version"] == 1
    assert cuerpo["ingested_at"] == "2026-11-02T12:00:00.123Z"
    assert set(cuerpo) == {"schema_version", "source", "ingested_at", "mode", "event"}
    resultado = validar_mensaje(clave, valor, "live")
    assert isinstance(resultado, MensajeValido)
    assert evento == original
    assert resultado.mensaje["event"] == original


def test_construir_mensaje_convierte_otras_zonas_a_utc():
    madrid = timezone(timedelta(hours=1))
    _, valor = construir_mensaje(base()["event"], "synthetic-smoke", "live", datetime(2026, 11, 2, 13, 0, tzinfo=madrid))
    assert json.loads(valor)["ingested_at"] == "2026-11-02T12:00:00.000Z"


def test_construir_mensaje_conserva_caracteres_unicode():
    _, valor = construir_mensaje(base()["event"], "synthetic-smoke", "live", datetime.now(timezone.utc))
    assert "SINTÉTICO".encode("utf-8") in valor


def test_construir_mensaje_sin_id_falla():
    with pytest.raises(ValueError):
        construir_mensaje({"properties": {}}, "synthetic-smoke", "live", datetime.now(timezone.utc))
