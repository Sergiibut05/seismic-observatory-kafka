"""Fuentes de una versión guardada (013): las del v2 o, en v1, la del mensaje."""

from observatorio.consumer.persistencia import fuentes_de


def test_v2_ordenadas():
    original = {"schema_version": 2, "fuentes": [{"fuente": "usgs"}, {"fuente": "emsc"}]}
    assert fuentes_de(original, "emsc") == ["emsc", "usgs"]


def test_v1_la_del_mensaje():
    assert fuentes_de({"schema_version": 1, "event": {}}, "usgs") == ["usgs"]
    assert fuentes_de({}, "synthetic-smoke") == ["synthetic-smoke"]


def test_lista_rara_no_rompe():
    assert fuentes_de({"fuentes": "usgs"}, "usgs") == ["usgs"]
    assert fuentes_de({"fuentes": [5, {"fuente": "emsc"}]}, "emsc") == ["emsc"]
