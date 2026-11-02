"""El país sale del polígono, nunca del texto `place`."""

import json

from observatorio.common.catalogo import SIN_PAIS, construir_indice

CUADRADO = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
PEQUENO = {"type": "Polygon", "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]]}


def feature(codigo, geometria, **propiedades):
    props = {"ADM0_A3": codigo, "NAME_ES": codigo}
    props.update(propiedades)
    return {"type": "Feature", "properties": props, "geometry": geometria}


def indice(tmp_path, features):
    ruta = tmp_path / "paises.geojson"
    ruta.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return construir_indice(ruta)


def test_punto_dentro_fuera_y_place_ignorado(tmp_path):
    paises = indice(tmp_path, [feature("AAA", CUADRADO, NAME_ES="País A", place="No es un país")])
    assert paises.asignar(0.5, 0.5) == ("AAA", "País A")
    assert paises.asignar(50, 50) == (None, SIN_PAIS)


def test_si_dos_poligonos_contienen_el_punto_gana_el_menor(tmp_path):
    paises = indice(tmp_path, [feature("GRANDE", CUADRADO, NAME_ES="Grande"), feature("CHICO", PEQUENO, NAME_ES="Chico")])
    assert paises.asignar(1.5, 1.5) == ("CHICO", "Chico")
    assert paises.asignar(5, 5) == ("GRANDE", "Grande")
