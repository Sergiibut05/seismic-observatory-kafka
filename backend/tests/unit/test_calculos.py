"""Pruebas de los cálculos puros de la API (feature 005): horas, intervalos, comparación, mapa, umbral."""

import re
from datetime import datetime, timedelta, timezone

import pytest

from observatorio.api.calculos import (
    BORDES_MAGNITUD,
    BORDES_PROFUNDIDAD,
    MAPA_TOPE,
    armar_intervalos,
    comparar,
    desactualizado,
    geojson_mapa,
    rellenar_horas,
    reproducido_en,
)

UTC = timezone.utc
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def utc(*args, **kw):
    return datetime(*args, tzinfo=UTC, **kw)


# --- rellenar_horas (AC-5) -------------------------------------------------


def test_seis_horas_con_eventos_en_tres_dan_seis_ventanas_y_tres_ceros():
    filas = [(utc(2026, 11, 2, 7), 2), (utc(2026, 11, 2, 9), 1), (utc(2026, 11, 2, 11), 5)]
    ventanas = rellenar_horas(filas, utc(2026, 11, 2, 6), utc(2026, 11, 2, 12))
    assert [v["inicio"] for v in ventanas] == [f"2026-11-02T{h:02d}:00:00.000Z" for h in range(6, 12)]
    assert [v["recuento"] for v in ventanas] == [0, 2, 0, 1, 0, 5]


def test_ventanas_distintas_para_10_59_59_999_y_11_00_00_000():
    # La consulta SQL agrupa con date_trunc; aquí se comprueba que ambas horas existen por separado.
    filas = [(utc(2026, 11, 2, 10), 1), (utc(2026, 11, 2, 11), 1)]
    ventanas = rellenar_horas(filas, utc(2026, 11, 2, 10), utc(2026, 11, 2, 12))
    assert [v["recuento"] for v in ventanas] == [1, 1]
    assert ventanas[0]["inicio"] != ventanas[1]["inicio"]


def test_hasta_exclusivo_no_abre_la_ventana_siguiente():
    ventanas = rellenar_horas([], utc(2026, 11, 2, 6), utc(2026, 11, 2, 7))
    assert len(ventanas) == 1
    ventanas = rellenar_horas([], utc(2026, 11, 2, 6), utc(2026, 11, 2, 7, 0, 0, 1000))
    assert len(ventanas) == 2


def test_extremos_parciales_cuentan_como_ventana():
    ventanas = rellenar_horas([], utc(2026, 11, 2, 6, 30), utc(2026, 11, 2, 8, 15))
    assert [v["inicio"][11:13] for v in ventanas] == ["06", "07", "08"]


def test_sin_eventos_todo_ceros_nunca_lista_vacia():
    ventanas = rellenar_horas([], utc(2026, 11, 2, 0), utc(2026, 11, 3, 0))
    assert len(ventanas) == 24 and all(v["recuento"] == 0 for v in ventanas)


def test_horas_de_otra_zona_se_normalizan_a_utc():
    madrid = timezone(timedelta(hours=1))
    filas = [(datetime(2026, 11, 2, 8, tzinfo=madrid), 4)]
    ventanas = rellenar_horas(filas, utc(2026, 11, 2, 6), utc(2026, 11, 2, 9))
    assert [v["recuento"] for v in ventanas] == [0, 4, 0]
    assert all(ISO.match(v["inicio"]) for v in ventanas)


def test_31_dias_dan_744_o_745_ventanas():
    ventanas = rellenar_horas([], utc(2026, 10, 1), utc(2026, 11, 1))
    assert len(ventanas) == 744


# --- armar_intervalos ------------------------------------------------------


def test_intervalos_de_magnitud_con_ceros_y_extremos_abiertos():
    intervalos, sin_valor, total = armar_intervalos([(5, 3), (10, 1)], BORDES_MAGNITUD)
    assert len(intervalos) == 11
    assert intervalos[0] == {"desde": None, "hasta": 0, "etiqueta": "< 0", "recuento": 0}
    assert intervalos[5] == {"desde": 4, "hasta": 5, "etiqueta": "4–5", "recuento": 3}
    assert intervalos[10] == {"desde": 9, "hasta": None, "etiqueta": "≥ 9", "recuento": 1}
    assert sum(i["recuento"] for i in intervalos) == 4
    assert (sin_valor, total) == (0, 4)


def test_magnitudes_negativas_caen_en_el_primer_intervalo():
    intervalos, _, total = armar_intervalos([(0, 7)], BORDES_MAGNITUD)
    assert intervalos[0]["recuento"] == 7 and total == 7


def test_el_nulo_va_a_sin_valor_y_no_a_un_intervalo():
    intervalos, sin_valor, total = armar_intervalos([(None, 2), (1, 1)], BORDES_MAGNITUD)
    assert sin_valor == 2
    assert sum(i["recuento"] for i in intervalos) == 1
    assert intervalos[0]["recuento"] == 0 and intervalos[1]["recuento"] == 1  # el nulo no es un 0
    assert total == 3


def test_intervalos_vacios_son_todo_ceros():
    intervalos, sin_valor, total = armar_intervalos([], BORDES_PROFUNDIDAD)
    assert len(intervalos) == 9 and (sin_valor, total) == (0, 0)
    assert all(i["recuento"] == 0 for i in intervalos)


def test_intervalos_de_profundidad():
    intervalos, _, _ = armar_intervalos([(3, 1)], BORDES_PROFUNDIDAD)
    assert [i["etiqueta"] for i in intervalos] == [
        "< 0", "0–10", "10–30", "30–70", "70–150", "150–300", "300–500", "500–700", "≥ 700"
    ]
    assert intervalos[3]["recuento"] == 1


# --- comparar (AC-6) -------------------------------------------------------


def test_media_de_18302_eventos_en_365_dias():
    historico, cociente = comparar(100, 18302, True)
    assert historico["estado"] == "cargado"
    assert historico["eventos"] == 18302 and historico["dias"] == 365
    assert historico["media_diaria"] == pytest.approx(50.14, abs=0.01)
    assert cociente == pytest.approx(100 / (18302 / 365), abs=0.01)


def test_media_cero_no_falla_y_el_cociente_es_nulo():
    historico, cociente = comparar(3, 0, True)
    assert historico["media_diaria"] == 0 and historico["eventos"] == 0
    assert historico["estado"] == "cargado"
    assert cociente is None


def test_cociente_cero_si_no_hay_eventos_recientes():
    _, cociente = comparar(0, 365, True)
    assert cociente == 0


def test_historico_no_cargado_da_nulos_no_ceros():
    historico, cociente = comparar(12, None, False)
    assert historico == {"estado": "no_cargado", "eventos": None, "dias": 365, "media_diaria": None}
    assert cociente is None
    historico, cociente = comparar(12, 0, False)
    assert historico["eventos"] is None and cociente is None


# --- geojson_mapa ----------------------------------------------------------


def fila(n, magnitud=4.5, profundidad=10.0):
    return (
        f"us{n:04d}",
        utc(2026, 11, 2, 10, 0, 0, 123000),
        utc(2026, 11, 2, 10, 5),
        magnitud,
        profundidad,
        -122.5,
        37.25,
        "Estados Unidos",
        False,
        utc(2026, 11, 2, 10, 6, 0, 456000),
    )


GENERADO = utc(2026, 11, 2, 12)


def test_geojson_con_coordenadas_lon_lat_y_propiedades():
    datos = geojson_mapa([fila(1)], 1, MAPA_TOPE, GENERADO)
    assert datos["type"] == "FeatureCollection"
    punto = datos["features"][0]
    assert punto["geometry"] == {"type": "Point", "coordinates": [-122.5, 37.25]}
    assert punto["properties"] == {
        "event_id": "us0001",
        "ocurrencia": "2026-11-02T10:00:00.123Z",
        "updated": "2026-11-02T10:05:00.000Z",
        "magnitud": 4.5,
        "profundidad": 10.0,
        "pais_nombre": "Estados Unidos",
        "sintetico": False,
        "reproducido_en": None,
    }
    assert (datos["total"], datos["devueltos"], datos["limite"], datos["truncado"]) == (1, 1, MAPA_TOPE, False)
    assert datos["generated_at"] == "2026-11-02T12:00:00.000Z"
    assert datos["modo"] == "live"


def test_mapa_replay_trae_modo_y_el_tiempo_de_reproduccion():
    datos = geojson_mapa([fila(1)], 1, MAPA_TOPE, GENERADO, "replay")
    assert datos["modo"] == "replay"
    propiedades = datos["features"][0]["properties"]
    assert propiedades["reproducido_en"] == "2026-11-02T10:06:00.456Z"
    # El tiempo original no se toca: sigue siendo el de ocurrencia.
    assert propiedades["ocurrencia"] == "2026-11-02T10:00:00.123Z"


def test_mapa_live_no_expone_la_ingesta_como_reproduccion():
    datos = geojson_mapa([fila(1)], 1, MAPA_TOPE, GENERADO, "live")
    assert datos["features"][0]["properties"]["reproducido_en"] is None


def test_mapa_con_modo_ajeno_es_un_error_de_programacion():
    with pytest.raises(ValueError):
        geojson_mapa([fila(1)], 1, MAPA_TOPE, GENERADO, "otro")


def test_reproducido_en_solo_en_replay():
    ingesta = utc(2026, 11, 2, 10, 6, 0, 456000)
    assert reproducido_en(ingesta, "live") is None
    assert reproducido_en(ingesta, "replay") == "2026-11-02T10:06:00.456Z"
    assert reproducido_en(None, "replay") is None


def test_nulos_se_conservan_nunca_como_cero():
    punto = geojson_mapa([fila(1, magnitud=None, profundidad=None)], 1, MAPA_TOPE, GENERADO)["features"][0]
    assert punto["properties"]["magnitud"] is None and punto["properties"]["profundidad"] is None


def test_tope_marca_truncado_y_conserva_el_total_real():
    filas = [fila(n) for n in range(3)]
    datos = geojson_mapa(filas, 12_345, 3, GENERADO)
    assert datos["truncado"] is True
    assert (datos["total"], datos["devueltos"], datos["limite"]) == (12_345, 3, 3)


def test_justo_en_el_tope_no_se_trunca():
    datos = geojson_mapa([fila(n) for n in range(3)], 3, 3, GENERADO)
    assert datos["truncado"] is False


def test_el_total_nunca_es_menor_que_lo_devuelto():
    assert geojson_mapa([fila(1), fila(2)], 1, 5, GENERADO)["total"] == 2


def test_mapa_vacio():
    datos = geojson_mapa([], 0, MAPA_TOPE, GENERADO)
    assert datos["features"] == [] and datos["total"] == 0 and datos["truncado"] is False


# --- desactualizado (AC-10) ------------------------------------------------

AHORA = utc(2026, 11, 2, 12, 0, 0)


def test_sin_ingesta_correcta_esta_desactualizado():
    assert desactualizado(None, AHORA, 300) is True


def test_dentro_del_umbral_no():
    assert desactualizado(AHORA - timedelta(seconds=60), AHORA, 300) is False


def test_en_el_umbral_exacto_no_y_pasado_si():
    assert desactualizado(AHORA - timedelta(seconds=300), AHORA, 300) is False
    assert desactualizado(AHORA - timedelta(seconds=300, milliseconds=1), AHORA, 300) is True
