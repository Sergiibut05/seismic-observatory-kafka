"""Partición de intervalos y deduplicación del histórico, sin red."""

import json
from datetime import datetime, timezone

from observatorio.historico import cubrir, deduplicar, es_exceso, partir

INICIO = datetime(2025, 1, 1, tzinfo=timezone.utc)
FIN = datetime(2025, 2, 1, tzinfo=timezone.utc)


def feature(event_id, updated):
    return {"id": event_id, "properties": {"updated": updated, "time": updated, "type": "earthquake"}}


def test_parte_el_intervalo_por_la_mitad():
    (a1, a2), (b1, b2) = partir(INICIO, FIN)
    assert a1 == INICIO and b2 == FIN and a2 == b1
    assert a1 < a2 < b2


def test_detecta_el_rechazo_de_usgs_por_exceso():
    assert es_exceso(400, b"Error 400: more than 20000 results")
    assert not es_exceso(200, b'{"features":[]}')
    assert not es_exceso(404, b"20000")


def test_el_extremo_compartido_se_queda_una_vez():
    unicos, repetidos = deduplicar([feature("us1", 1), feature("us1", 1), feature("us1", 2)])
    assert [e["properties"]["updated"] for e in unicos] == [1, 2]
    assert repetidos == 1


def test_un_exceso_parte_la_consulta_en_vez_de_truncar():
    cuerpo = json.dumps({"features": [feature("us1", 1)]}).encode()

    def pedir(url):
        if "2025-01-01" in url and "2025-02-01" in url:
            return 400, b"The result set is too large: more than 20000"
        return 200, cuerpo

    features, consultas = cubrir(INICIO, FIN, pedir)
    assert len(features) == 2
    assert consultas[0]["features"] == "partido"
    assert all(c["http_status"] == 200 for c in consultas[1:])
