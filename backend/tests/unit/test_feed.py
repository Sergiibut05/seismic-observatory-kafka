"""Clasificación del feed y retención del original, sin red ni base de datos."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from observatorio.producer.feed import clasificar, conservar_original, es_transitorio

AHORA = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def evento(event_id="us1", updated=1000, tipo="earthquake"):
    return {"type": "Feature", "id": event_id, "properties": {"type": tipo, "updated": updated, "mag": 1.2}}


def test_publica_nuevo_y_omite_el_ya_publicado():
    resultado = clasificar([evento(), evento("us2", 2000)], {("us1", 1000)})
    assert [e["id"] for e in resultado.publicar] == ["us2"]
    assert resultado.omitidos == 1
    assert resultado.exclusiones == ()


def test_una_revision_posterior_se_publica():
    resultado = clasificar([evento(updated=2000)], {("us1", 1000)})
    assert [e["id"] for e in resultado.publicar] == ["us1"]


def test_el_mismo_evento_repetido_en_el_feed_se_publica_una_vez():
    resultado = clasificar([evento(), evento()], set())
    assert len(resultado.publicar) == 1
    assert resultado.omitidos == 1


def test_lo_que_no_es_terremoto_queda_excluido_con_motivo():
    resultado = clasificar([evento(tipo="quarry blast")], set())
    assert resultado.publicar == ()
    assert resultado.exclusiones[0].motivo == "tipo_no_terremoto"
    assert resultado.exclusiones[0].event_id == "us1"


def test_sin_id_o_updated_invalido_no_se_publican():
    sin_id = {"properties": {"type": "earthquake", "updated": 1}}
    negativo = evento(updated=True)
    resultado = clasificar([sin_id, negativo, "basura"], set())
    assert resultado.publicar == ()
    assert [e.motivo for e in resultado.exclusiones] == ["sin_id", "updated_invalido", "feature_no_objeto"]


def test_http_transitorio():
    assert es_transitorio(429)
    assert es_transitorio(503)
    assert not es_transitorio(200)
    assert not es_transitorio(404)


def test_no_repite_una_copia_identica_y_borra_lo_viejo(tmp_path: Path):
    viejo = tmp_path / "20000101T000000Z-aaa.geojson"
    viejo.write_bytes(b'{"features":[]}')
    hace_tres_dias = (AHORA - timedelta(hours=72)).timestamp()
    import os

    os.utime(viejo, (hace_tres_dias, hace_tres_dias))
    sha, nueva = conservar_original(tmp_path, b'{"features":[1]}', AHORA, 48)
    assert nueva
    otra_sha, otra_nueva = conservar_original(tmp_path, b'{"features":[1]}', AHORA, 48)
    assert sha == otra_sha
    assert not otra_nueva
    assert list(tmp_path.glob("*.geojson")) == [tmp_path / f"20261102T120000Z-{sha}.geojson"]
