"""Pruebas de la carga y validación del catálogo de países (US5, FR-020, FR-021, R-18)."""

import json
from pathlib import Path

import pytest

from observatorio.common.catalogo import Catalogo, CatalogoError, cargar_catalogo

CUADRADO = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
OTRO_CUADRADO = {"type": "Polygon", "coordinates": [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]]}
MULTI = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]],
        [[[20, 20], [21, 20], [21, 21], [20, 21], [20, 20]]],
    ],
}
# Lazo: autointersección (topológicamente inválido) pero sigue siendo un Polygon.
LAZO = {"type": "Polygon", "coordinates": [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]}


def feature(adm0="AAA", geometria=CUADRADO, **propiedades):
    props = {"ADM0_A3": adm0, "NAME_ES": "Pais"}
    props.update(propiedades)
    return {"type": "Feature", "properties": props, "geometry": geometria}


def escribir(tmp_path, features, nombre="paises.geojson"):
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return ruta


# --- caso válido ----------------------------------------------------------


def test_catalogo_valido(tmp_path):
    ruta = escribir(tmp_path, [feature("AAA"), feature("BBB", OTRO_CUADRADO), feature("CCC", MULTI)])
    catalogo = cargar_catalogo(ruta)
    assert catalogo == Catalogo(total=3, fuente=str(ruta), geometrias_invalidas=0)


def test_acepta_ruta_como_texto(tmp_path):
    ruta = escribir(tmp_path, [feature("AAA")])
    assert cargar_catalogo(str(ruta)).total == 1


# --- un caso por motivo ---------------------------------------------------


def motivo_de(ruta):
    with pytest.raises(CatalogoError) as exc:
        cargar_catalogo(ruta)
    return exc.value


def test_catalogo_ausente_incluye_la_ruta_esperada(tmp_path):
    ruta = tmp_path / "no_existe.geojson"
    error = motivo_de(ruta)
    assert error.motivo == "catalogo_ausente"
    assert str(ruta) in error.detalle


def test_catalogo_ilegible_json_roto(tmp_path):
    ruta = tmp_path / "roto.geojson"
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert motivo_de(ruta).motivo == "catalogo_ilegible"


def test_catalogo_ilegible_bytes_no_utf8(tmp_path):
    ruta = tmp_path / "bin.geojson"
    ruta.write_bytes(b"\xff\xfe\x00basura")
    assert motivo_de(ruta).motivo == "catalogo_ilegible"


@pytest.mark.parametrize(
    "contenido",
    [
        {"type": "Feature", "properties": {}, "geometry": CUADRADO},
        {"type": "GeometryCollection", "geometries": []},
        [],
        "texto",
        {"type": "FeatureCollection"},
        {"type": "FeatureCollection", "features": "no es lista"},
    ],
)
def test_catalogo_ilegible_no_es_featurecollection(tmp_path, contenido):
    ruta = tmp_path / "otro.geojson"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    assert motivo_de(ruta).motivo == "catalogo_ilegible"


def test_catalogo_ilegible_si_la_ruta_es_un_directorio(tmp_path):
    assert motivo_de(tmp_path).motivo == "catalogo_ilegible"


def test_catalogo_vacio(tmp_path):
    assert motivo_de(escribir(tmp_path, [])).motivo == "catalogo_vacio"


@pytest.mark.parametrize(
    "geometria",
    [
        {"type": "Point", "coordinates": [0, 0]},
        {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        None,
    ],
)
def test_geometria_no_poligonal(tmp_path, geometria):
    ruta = escribir(tmp_path, [feature("AAA"), feature("BBB", geometria)])
    error = motivo_de(ruta)
    assert error.motivo == "geometria_no_poligonal"
    assert "BBB" in error.detalle


@pytest.mark.parametrize("propiedades", [{}, {"ADM0_A3": None}, {"ADM0_A3": ""}, {"ADM0_A3": 5}])
def test_adm0_a3_ausente(tmp_path, propiedades):
    sin_codigo = {"type": "Feature", "properties": propiedades, "geometry": CUADRADO}
    ruta = escribir(tmp_path, [feature("AAA"), sin_codigo])
    assert motivo_de(ruta).motivo == "adm0_a3_ausente"


def test_adm0_a3_ausente_sin_properties(tmp_path):
    sin_props = {"type": "Feature", "properties": None, "geometry": CUADRADO}
    assert motivo_de(escribir(tmp_path, [sin_props])).motivo == "adm0_a3_ausente"


def test_adm0_a3_repetido(tmp_path):
    ruta = escribir(tmp_path, [feature("AAA"), feature("BBB", OTRO_CUADRADO), feature("AAA", MULTI)])
    error = motivo_de(ruta)
    assert error.motivo == "adm0_a3_repetido"
    assert "AAA" in error.detalle


# --- geometrías inválidas topológicamente ---------------------------------


def test_geometria_invalida_no_bloquea_y_se_cuenta(tmp_path):
    ruta = escribir(tmp_path, [feature("AAA"), feature("BBB", LAZO), feature("CCC", MULTI)])
    catalogo = cargar_catalogo(ruta)
    assert catalogo.total == 3
    assert catalogo.geometrias_invalidas == 1


# --- error de catálogo ----------------------------------------------------


def test_catalogo_error_expone_motivo_y_detalle():
    error = CatalogoError("catalogo_vacio", "sin entidades")
    assert error.motivo == "catalogo_vacio"
    assert error.detalle == "sin entidades"
    assert "catalogo_vacio" in str(error)


# --- integración: catálogo entregado (se salta si no está montado) --------

RUTA_REAL = Path("/catalogo/paises.geojson")


@pytest.mark.skipif(not RUTA_REAL.exists(), reason="catálogo no montado en /catalogo")
def test_catalogo_entregado_tiene_242_paises():
    catalogo = cargar_catalogo(RUTA_REAL)
    assert catalogo.total == 242
    assert catalogo.fuente == str(RUTA_REAL)
    assert catalogo.geometrias_invalidas == 0
