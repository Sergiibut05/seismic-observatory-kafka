"""Pruebas del evento sintético de la prueba de humo (R-11)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from observatorio.common.contrato import MensajeValido, es_sintetico, validar_mensaje
from observatorio.producer.evento_sintetico import SOURCE_SINTETICO, evento_sintetico, mensaje_sintetico

EJEMPLO = Path(__file__).resolve().parent.parent / "fixtures" / "mensaje_v1_ejemplo.json"
AHORA = datetime(2026, 11, 2, 12, 34, 56, 789000, tzinfo=timezone.utc)


def reloj():
    return AHORA


def test_valores_por_defecto():
    evento = evento_sintetico()
    assert evento["id"] == "synthetic-smoke-0001"
    assert evento["properties"]["updated"] == 1767225600000
    assert SOURCE_SINTETICO == "synthetic-smoke"
    assert "SINTÉTICO" in evento["properties"]["place"]
    assert evento["properties"]["mag"] is not None
    lon, lat, profundidad = evento["geometry"]["coordinates"]
    assert -180 <= lon <= 180 and -90 <= lat <= 90 and profundidad is not None


def test_el_evento_por_defecto_coincide_con_el_ejemplo_del_contrato():
    esperado = json.loads(EJEMPLO.read_text(encoding="utf-8"))["event"]
    assert evento_sintetico() == esperado


def test_unico_anade_sufijo_con_la_hora_utc():
    evento = evento_sintetico(unico=True, ahora=reloj)
    assert evento["id"] == "synthetic-smoke-20261102T123456Z"
    assert evento["id"].startswith("synthetic-smoke-")
    assert es_sintetico(evento["id"])


def test_dos_llamadas_por_defecto_generan_la_misma_version():
    a, b = evento_sintetico(), evento_sintetico()
    assert (a["id"], a["properties"]["updated"]) == (b["id"], b["properties"]["updated"])


def test_unico_en_instantes_distintos_genera_ids_distintos():
    otro = datetime(2026, 11, 2, 12, 34, 57, tzinfo=timezone.utc)
    assert evento_sintetico(True, lambda: AHORA)["id"] != evento_sintetico(True, lambda: otro)["id"]


def test_el_mensaje_pasa_la_validacion():
    for unico in (False, True):
        clave, valor = mensaje_sintetico(unico=unico, ahora=reloj)
        resultado = validar_mensaje(clave, valor, "live")
        assert isinstance(resultado, MensajeValido), resultado
        assert resultado.sintetico is True
        assert resultado.source == "synthetic-smoke"
        assert resultado.ingested_at == AHORA.replace(microsecond=789000)


def test_cada_llamada_devuelve_un_objeto_nuevo():
    a = evento_sintetico()
    a["properties"]["mag"] = 99
    assert evento_sintetico()["properties"]["mag"] == 1.0
