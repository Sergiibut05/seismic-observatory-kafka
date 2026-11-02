"""Contenido utilizable: no se rellenan nulos y lo que no se puede situar se rechaza."""

from observatorio.consumer.calidad import Contenido, evaluar
from observatorio.common.contrato import Rechazo


def mensaje(coordenadas, time=1_700_000_000_000, mag=4.2, propiedades=None):
    props = {"time": time, "updated": time, "mag": mag, "place": "este texto no es un país"}
    if propiedades is not None:
        props = propiedades
    return {"event": {"id": "us1", "properties": props, "geometry": {"type": "Point", "coordinates": coordenadas}}}


def test_acepta_magnitud_y_profundidad_negativas_y_no_inventa_ceros():
    contenido = evaluar(mensaje([-3.7, 40.4, -1.5], mag=-0.4))
    assert isinstance(contenido, Contenido)
    assert contenido.magnitud == -0.4
    assert contenido.profundidad == -1.5
    assert contenido.longitud == -3.7 and contenido.latitud == 40.4

    sin_mag = evaluar(mensaje([-3.7, 40.4], propiedades={"time": 1_700_000_000_000}))
    assert isinstance(sin_mag, Contenido)
    assert sin_mag.magnitud is None and sin_mag.profundidad is None


def test_sin_punto_o_fuera_de_rango_se_rechaza():
    assert evaluar({"event": {"properties": {"time": 1}, "geometry": {"type": "Polygon", "coordinates": []}}}).motivo == "geometria_inutilizable"
    assert evaluar(mensaje([181, 0])).motivo == "coordenadas_fuera_de_rango"
    assert evaluar(mensaje([-3.7, 40.4], propiedades={"time": "ayer"})).motivo == "tiempo_invalido"
    assert evaluar(mensaje([-3.7, 40.4], mag="4")).motivo == "magnitud_invalida"
    rechazo = evaluar(mensaje([-3.7, 40.4, "no"]))
    assert isinstance(rechazo, Rechazo)
    assert rechazo.motivo == "profundidad_invalida"
