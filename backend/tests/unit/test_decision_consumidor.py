"""Pruebas de la decisión del consumidor, sin infraestructura (R-09, R-15)."""

import json
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from observatorio.consumer.decision import (
    ESQUEMAS_DESTINO,
    Aceptar,
    Rechazar,
    clasificar_error_bd,
    decidir,
    resultado_escritura,
)

EJEMPLO = Path(__file__).resolve().parent.parent / "fixtures" / "mensaje_v1_ejemplo.json"


def registro(valor=None, clave=b"synthetic-smoke-0001", topic="eventos.live", particion=2, offset=5):
    if valor is None:
        valor = EJEMPLO.read_bytes()
    return SimpleNamespace(key=clave, value=valor, topic=topic, partition=particion, offset=offset)


# --- decidir --------------------------------------------------------------


def test_registro_valido_se_acepta_en_el_esquema_live():
    decision = decidir(registro(), "live")
    assert isinstance(decision, Aceptar)
    assert decision.esquema == "live"
    assert decision.version.event_id == "synthetic-smoke-0001"
    assert decision.version.sintetico is True
    assert decision.version.updated.isoformat() == "2026-01-01T00:00:00+00:00"


def test_registro_invalido_se_rechaza_con_motivo():
    decision = decidir(registro(valor=b"{roto"), "live")
    assert isinstance(decision, Rechazar)
    assert decision.motivo == "json_ilegible"
    assert decision.detalle


def test_rechazo_conserva_el_evento_si_se_conoce():
    decision = decidir(registro(clave=b"otra"), "live")
    assert isinstance(decision, Rechazar)
    assert decision.motivo == "clave_distinta_de_id"
    assert decision.event_id == "synthetic-smoke-0001"
    assert decision.updated == 1767225600000


def test_valor_nulo_se_rechaza():
    decision = decidir(SimpleNamespace(key=b"k", value=None), "live")
    assert isinstance(decision, Rechazar)
    assert decision.motivo == "valor_ausente"


def test_replay_en_el_topic_live_se_rechaza():
    cuerpo = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    cuerpo["mode"] = "replay"
    decision = decidir(registro(valor=json.dumps(cuerpo).encode()), "live")
    assert isinstance(decision, Rechazar)
    assert decision.motivo == "mode_no_corresponde_al_topic"


def test_el_esquema_destino_sale_de_una_lista_cerrada():
    assert set(ESQUEMAS_DESTINO) == {"live", "replay"}
    cuerpo = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    cuerpo["mode"] = "replay"
    decision = decidir(registro(valor=json.dumps(cuerpo).encode()), "replay")
    assert isinstance(decision, Aceptar)
    assert decision.esquema == "replay"


def test_modo_de_topic_desconocido_es_un_error():
    with pytest.raises(ValueError):
        decidir(registro(), "'; DROP SCHEMA live; --")


# --- resultado_escritura --------------------------------------------------


def test_resultado_escritura():
    assert resultado_escritura(1) == "persistido"
    assert resultado_escritura(0) == "omitido"


@pytest.mark.parametrize("filas", [-1, 2, None])
def test_resultado_escritura_inesperado(filas):
    with pytest.raises(ValueError):
        resultado_escritura(filas)


# --- clasificar_error_bd --------------------------------------------------


@pytest.mark.parametrize(
    "excepcion",
    [psycopg.OperationalError("caído"), psycopg.InterfaceError("conexión cerrada"), psycopg.errors.AdminShutdown("x")],
)
def test_errores_de_conexion_se_reintentan(excepcion):
    assert clasificar_error_bd(excepcion) == "reintentar"


@pytest.mark.parametrize(
    "excepcion",
    [
        psycopg.errors.UntranslatableCharacter("\\u0000"),
        psycopg.errors.DataError("dato"),
        psycopg.errors.CheckViolation("check"),
        psycopg.errors.IntegrityError("integridad"),
        psycopg.errors.StringDataRightTruncation("largo"),
    ],
)
def test_errores_de_dato_van_a_cuarentena(excepcion):
    assert clasificar_error_bd(excepcion) == "cuarentena"


@pytest.mark.parametrize(
    "excepcion",
    [RuntimeError("boom"), KeyError("x"), psycopg.errors.UndefinedTable("t"), psycopg.errors.SyntaxError("s")],
)
def test_el_resto_es_desconocido(excepcion):
    assert clasificar_error_bd(excepcion) == "desconocido"
