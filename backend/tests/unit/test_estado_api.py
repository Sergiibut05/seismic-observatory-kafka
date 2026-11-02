"""Pruebas de `armar_estado` (FR-023, contracts/api.openapi.yaml)."""

import re
from datetime import datetime, timezone

from observatorio.api.estado import armar_estado, iso_utc

AHORA = datetime(2026, 11, 2, 12, 0, 5, tzinfo=timezone.utc)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

CLAVES = {"base_de_datos", "eventos_reales", "eventos_sinteticos", "ultimo_evento", "generated_at"}
CLAVES_ULTIMO = {"event_id", "updated", "source", "sintetico", "processed_at"}


def ultimo(**cambios):
    fila = {
        "event_id": "synthetic-smoke-0001",
        "updated": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "source": "synthetic-smoke",
        "sintetico": True,
        "processed_at": datetime(2026, 11, 2, 12, 0, 0, 456000, tzinfo=timezone.utc),
    }
    fila.update(cambios)
    return (fila["event_id"], fila["updated"], fila["source"], fila["sintetico"], fila["processed_at"])


def test_base_conectada_con_eventos():
    estado = armar_estado((0, 1), ultimo(), True, AHORA)
    assert set(estado) == CLAVES
    assert estado["base_de_datos"] == "conectada"
    assert estado["eventos_reales"] == 0 and isinstance(estado["eventos_reales"], int)
    assert estado["eventos_sinteticos"] == 1
    assert set(estado["ultimo_evento"]) == CLAVES_ULTIMO
    assert estado["ultimo_evento"]["event_id"] == "synthetic-smoke-0001"
    assert estado["ultimo_evento"]["source"] == "synthetic-smoke"
    assert estado["ultimo_evento"]["sintetico"] is True


def test_los_instantes_van_en_iso_utc_con_z_y_milisegundos():
    estado = armar_estado((0, 1), ultimo(), True, AHORA)
    assert estado["generated_at"] == "2026-11-02T12:00:05.000Z"
    assert estado["ultimo_evento"]["updated"] == "2026-01-01T00:00:00.000Z"
    assert estado["ultimo_evento"]["processed_at"] == "2026-11-02T12:00:00.456Z"
    for valor in (estado["generated_at"], estado["ultimo_evento"]["updated"], estado["ultimo_evento"]["processed_at"]):
        assert ISO.match(valor)


def test_un_instante_con_otra_zona_se_convierte_a_utc():
    from datetime import timedelta

    madrid = timezone(timedelta(hours=1))
    assert iso_utc(datetime(2026, 11, 2, 13, 0, 0, tzinfo=madrid)) == "2026-11-02T12:00:00.000Z"


def test_base_vacia():
    estado = armar_estado((0, 0), None, True, AHORA)
    assert estado["base_de_datos"] == "conectada"
    assert estado["eventos_reales"] == 0
    assert estado["eventos_sinteticos"] == 0
    assert estado["ultimo_evento"] is None


def test_base_caida_devuelve_none_nunca_cero():
    estado = armar_estado(None, None, False, AHORA)
    assert estado["base_de_datos"] == "fallida"
    assert estado["eventos_reales"] is None
    assert estado["eventos_sinteticos"] is None
    assert estado["ultimo_evento"] is None
    assert set(estado) == CLAVES


def test_base_caida_ignora_datos_residuales():
    # Aunque se pasaran datos, con la base caída el estado nunca debe mostrarlos como actuales.
    estado = armar_estado((5, 6), ultimo(), False, AHORA)
    assert estado["eventos_reales"] is None
    assert estado["eventos_sinteticos"] is None
    assert estado["ultimo_evento"] is None


def test_los_sinteticos_solo_se_suman_en_su_contador():
    estado = armar_estado((3, 2), ultimo(), True, AHORA)
    assert estado["eventos_reales"] == 3
    assert estado["eventos_sinteticos"] == 2


def test_ultimo_evento_real():
    fila = ultimo(event_id="us7000abcd", source="usgs", sintetico=False)
    estado = armar_estado((1, 0), fila, True, AHORA)
    assert estado["ultimo_evento"]["sintetico"] is False
    assert estado["ultimo_evento"]["source"] == "usgs"
