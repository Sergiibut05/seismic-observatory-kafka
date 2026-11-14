"""Normalización de los mensajes de fuente (USGS y EMSC) a `Informe`, con fixtures reales."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from observatorio.common.contrato import construir_mensaje
from observatorio.common.tiempo import iso_a_ms
from observatorio.fusion.normalizar import Descarte, Informe, fuente_del_topic, normalizar

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
AHORA = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def muestra(nombre):
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))["features"]


def mensaje(evento, fuente):
    return construir_mensaje(evento, fuente, "live", AHORA)


def norm(evento, fuente, topic=None):
    clave, valor = mensaje(evento, fuente)
    return normalizar(clave, valor, topic or f"eventos.{fuente}")


def test_usgs_real():
    evento = muestra("usgs_muestra.json")[0]
    informe = norm(evento, "usgs")
    assert isinstance(informe, Informe)
    assert informe.fuente == "usgs" and informe.id_origen == evento["id"]
    assert informe.tiempo_ms == evento["properties"]["time"]
    assert informe.updated_ms == evento["properties"]["updated"]
    assert (informe.longitud, informe.latitud, informe.profundidad) == tuple(evento["geometry"]["coordinates"])
    assert informe.magnitud == evento["properties"]["mag"]
    assert informe.lugar == evento["properties"]["place"]
    assert informe.original == evento
    assert informe.ingested_at == AHORA


def test_emsc_real_con_profundidad_positiva_y_horas_iso():
    evento = muestra("emsc_muestra.json")[0]
    p = evento["properties"]
    informe = norm(evento, "emsc")
    assert isinstance(informe, Informe)
    assert informe.id_origen == evento["id"] == p["unid"]
    assert informe.tiempo_ms == iso_a_ms(p["time"])
    assert informe.updated_ms == iso_a_ms(p["lastupdate"])
    assert informe.profundidad == p["depth"] > 0
    assert evento["geometry"]["coordinates"][2] == -p["depth"]
    assert (informe.latitud, informe.longitud) == (p["lat"], p["lon"])
    assert informe.tipo_magnitud == p["magtype"] and informe.lugar == p["flynn_region"]


def test_emsc_que_no_es_terremoto_conocido_se_descarta_con_motivo():
    evento = muestra("emsc_muestra.json")[2]
    assert evento["properties"]["evtype"] != "ke"
    resultado = norm(evento, "emsc")
    assert isinstance(resultado, Descarte) and resultado.motivo == "tipo_no_terremoto"
    assert resultado.fuente == "emsc" and resultado.id_origen == evento["id"]


def test_iso_con_fracciones_variables():
    assert iso_a_ms("2026-11-13T23:58:30.0Z") == iso_a_ms("2026-11-13T23:58:30Z")
    assert iso_a_ms("2026-11-14T00:07:46.525726Z") - iso_a_ms("2026-11-14T00:07:46Z") == 525
    assert iso_a_ms("2026-11-14T00:07:46") == iso_a_ms("2026-11-14T00:07:46Z")  # FDSN: UTC
    assert iso_a_ms("ayer") is None and iso_a_ms(None) is None and iso_a_ms(5) is None


def test_magnitud_y_profundidad_ausentes_quedan_en_nulo_no_en_cero():
    e = copy.deepcopy(muestra("emsc_muestra.json")[0])
    e["properties"]["mag"] = None
    e["properties"]["depth"] = None
    informe = norm(e, "emsc")
    assert informe.magnitud is None and informe.profundidad is None
    u = copy.deepcopy(muestra("usgs_muestra.json")[0])
    u["properties"]["mag"] = None
    u["geometry"]["coordinates"] = u["geometry"]["coordinates"][:2]
    informe = norm(u, "usgs")
    assert informe.magnitud is None and informe.profundidad is None


@pytest.mark.parametrize(
    ("fuente", "cambio", "motivo"),
    [
        ("usgs", lambda e: e["properties"].__setitem__("type", "quarry blast"), "tipo_no_terremoto"),
        ("usgs", lambda e: e["properties"].__setitem__("updated", "x"), "updated_invalido"),
        ("usgs", lambda e: e["properties"].__setitem__("time", None), "tiempo_invalido"),
        ("usgs", lambda e: e["geometry"].__setitem__("coordinates", [200, 10, 5]), "coordenadas_fuera_de_rango"),
        ("usgs", lambda e: e["geometry"].__setitem__("coordinates", ["a", 10]), "coordenadas_invalidas"),
        ("usgs", lambda e: e["geometry"].__setitem__("coordinates", [1, 1, "hondo"]), "profundidad_invalida"),
        ("usgs", lambda e: e["properties"].__setitem__("mag", "grande"), "magnitud_invalida"),
        ("emsc", lambda e: e["properties"].__setitem__("lastupdate", "nunca"), "updated_invalido"),
        ("emsc", lambda e: e["properties"].__setitem__("time", ""), "tiempo_invalido"),
        ("emsc", lambda e: e["properties"].update(lat=95.0), "coordenadas_fuera_de_rango"),
        ("emsc", lambda e: e["properties"].__setitem__("depth", "x"), "profundidad_invalida"),
        ("emsc", lambda e: e["properties"].__setitem__("mag", "grande"), "magnitud_invalida"),
    ],
)
def test_descartes_con_motivo(fuente, cambio, motivo):
    evento = copy.deepcopy(muestra(f"{fuente}_muestra.json")[0])
    cambio(evento)
    resultado = norm(evento, fuente)
    assert isinstance(resultado, Descarte), resultado
    assert resultado.motivo == motivo


def test_emsc_sin_lat_lon_en_properties_usa_la_geometria():
    e = copy.deepcopy(muestra("emsc_muestra.json")[1])
    lon, lat = e["geometry"]["coordinates"][:2]
    del e["properties"]["lat"], e["properties"]["lon"]
    informe = norm(e, "emsc")
    assert (informe.longitud, informe.latitud) == (lon, lat)


def test_el_sobre_se_valida_antes_que_el_evento():
    evento = muestra("usgs_muestra.json")[0]
    clave, valor = mensaje(evento, "usgs")
    assert normalizar(clave, valor, "eventos.emsc").motivo == "fuente_no_corresponde_al_topic"
    assert normalizar(b"otra", valor, "eventos.usgs").motivo == "clave_distinta_de_id"
    assert normalizar(clave, b"{no", "eventos.usgs").motivo == "json_ilegible"
    assert normalizar(clave, None, "eventos.usgs").motivo == "valor_ausente"
    assert normalizar(clave, valor, "eventos.otra").motivo == "topic_desconocido"
    sobre = json.loads(valor)
    sobre["mode"] = "replay"
    assert normalizar(clave, json.dumps(sobre).encode(), "eventos.usgs").motivo == "mode_invalido"
    sobre = json.loads(valor)
    sobre["extra"] = 1
    assert normalizar(clave, json.dumps(sobre).encode(), "eventos.usgs").motivo == "campo_ausente"


def test_fuente_del_topic():
    assert fuente_del_topic("eventos.usgs") == "usgs"
    assert fuente_del_topic("eventos.emsc") == "emsc"
    assert fuente_del_topic("eventos.live") is None
