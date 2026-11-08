"""Casos controlados de la feature 007 (FR-012): construcción pura, sin Kafka ni base de datos."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from observatorio.common.contrato import MensajeValido, Rechazo, es_sintetico, validar_mensaje
from observatorio.common.tiempo import iso_utc
from observatorio.consumer.calidad import Contenido, evaluar
from observatorio.producer import casos as c

UTC = timezone.utc
BASE = datetime(2026, 11, 8, 14, 0, 0, tzinfo=UTC)
BASE_MS = int(BASE.timestamp() * 1000)
INGESTA = datetime(2026, 11, 8, 14, 20, 30, 123000, tzinfo=UTC)


def construir(base=BASE, ingestado=INGESTA):
    return c.construir_casos(base, ingestado)


def evento(caso):
    return json.loads(caso.valor)["event"]


def propiedades(caso):
    return evento(caso)["properties"]


def por_nombre(nombre, casos=None):
    return [caso for caso in (casos or construir()) if caso.nombre == nombre]


def unico(nombre):
    (caso,) = por_nombre(nombre)
    return caso


# --- forma común -----------------------------------------------------------


def test_los_ocho_casos_del_plan():
    assert c.NOMBRES == (
        "nuevo", "reenvio", "revision", "antigua", "magnitud_nula",
        "coordenadas_invalidas", "mar", "profundidad_negativa",
    )
    assert {caso.nombre for caso in construir()} == set(c.NOMBRES)


def test_ids_con_prefijo_y_source_sintetico():
    for caso in construir():
        mensaje = json.loads(caso.valor)
        assert caso.clave.decode().startswith("synthetic-caso-"), caso.nombre
        assert evento(caso)["id"] == caso.clave.decode()
        assert mensaje["source"] == "synthetic-casos"
        assert mensaje["mode"] == "live" and mensaje["schema_version"] == 1
        assert es_sintetico(mensaje["source"]) and es_sintetico(evento(caso)["id"])


def test_el_evento_dice_que_es_sintetico():
    for caso in construir():
        assert "SINTÉTICO" in propiedades(caso)["place"], caso.nombre


def test_cada_mensaje_pasa_el_contrato():
    for caso in construir():
        resultado = validar_mensaje(caso.clave, caso.valor, "live")
        assert isinstance(resultado, MensajeValido), (caso.nombre, resultado)
        assert resultado.sintetico is True


def test_solo_el_caso_de_coordenadas_invalidas_cae_en_calidad():
    for caso in construir():
        mensaje = validar_mensaje(caso.clave, caso.valor, "live")
        contenido = evaluar(mensaje.mensaje)
        if caso.nombre == "coordenadas_invalidas":
            assert isinstance(contenido, Rechazo)
            assert contenido.motivo == "coordenadas_fuera_de_rango"
        else:
            assert isinstance(contenido, Contenido), (caso.nombre, contenido)


# --- determinismo ----------------------------------------------------------


def test_mismo_base_mismos_bytes_de_time_y_updated():
    otra_ingesta = INGESTA + timedelta(hours=3)
    for uno, otro in zip(construir(), construir(BASE, otra_ingesta), strict=True):
        assert uno.nombre == otro.nombre and uno.clave == otro.clave
        # El evento original (con `time` y `updated`) es idéntico; solo cambia `ingested_at`.
        assert evento(uno) == evento(otro)
        assert propiedades(uno)["time"] == propiedades(otro)["time"]
        assert propiedades(uno)["updated"] == propiedades(otro)["updated"]


def test_base_distinta_cambia_time_y_updated():
    siguiente = construir(BASE + timedelta(hours=1))
    assert propiedades(unico("nuevo"))["time"] != propiedades(siguiente[0])["time"]


def test_time_y_updated_en_milisegundos_epoch_enteros():
    nuevo = propiedades(unico("nuevo"))
    assert nuevo["time"] == BASE_MS and nuevo["updated"] == BASE_MS
    assert isinstance(nuevo["time"], int) and isinstance(nuevo["updated"], int)


def test_base_con_zona_distinta_es_el_mismo_instante():
    madrid = timezone(timedelta(hours=1))
    mismo = construir(BASE.astimezone(madrid))
    assert propiedades(mismo[0])["time"] == BASE_MS


def test_base_sin_zona_es_un_error():
    with pytest.raises(ValueError):
        c.construir_casos(datetime(2026, 11, 8, 14, 0, 0), INGESTA)


def test_la_base_por_defecto_es_la_hora_en_curso_truncada():
    ahora = datetime(2026, 11, 8, 14, 37, 12, 345000, tzinfo=UTC)
    assert c.base_por_defecto(ahora) == BASE


# --- casos concretos -------------------------------------------------------


def test_nuevo_en_espana():
    caso = unico("nuevo")
    assert caso.clave == b"synthetic-caso-nuevo"
    assert propiedades(caso)["mag"] == 3.4
    assert evento(caso)["geometry"]["coordinates"] == [-3.7, 40.4, 10]


def test_reenvio_es_el_mismo_evento_con_otra_ingesta():
    nuevo, reenvio = unico("nuevo"), unico("reenvio")
    assert reenvio.clave == nuevo.clave
    assert evento(reenvio) == evento(nuevo)
    ingesta_nuevo = json.loads(nuevo.valor)["ingested_at"]
    ingesta_reenvio = json.loads(reenvio.valor)["ingested_at"]
    assert ingesta_nuevo != ingesta_reenvio
    assert reenvio.valor != nuevo.valor


def test_revision_v2_es_60_segundos_posterior_y_cambia_de_pais():
    v1, v2 = por_nombre("revision")
    assert v1.clave == v2.clave == b"synthetic-caso-revision"
    assert propiedades(v2)["updated"] == propiedades(v1)["updated"] + 60_000
    assert propiedades(v1)["updated"] == BASE_MS
    assert propiedades(v1)["mag"] == 2.0 and propiedades(v2)["mag"] == 4.5
    assert evento(v1)["geometry"]["coordinates"] == [-3.7, 40.4, 10]
    assert evento(v2)["geometry"]["coordinates"] == [2.3, 48.9, 8]
    # Es el mismo terremoto: el tiempo de ocurrencia no cambia entre versiones.
    assert propiedades(v1)["time"] == propiedades(v2)["time"]


def test_antigua_es_60_segundos_anterior_y_va_despues_de_la_v2():
    casos = construir()
    posiciones = {(caso.nombre, i): i for i, caso in enumerate(casos)}
    v2_pos = max(i for (nombre, i) in posiciones if nombre == "revision")
    antigua = unico("antigua")
    assert casos.index(antigua) > v2_pos
    assert antigua.clave == b"synthetic-caso-revision"
    assert propiedades(antigua)["updated"] == BASE_MS - 60_000
    assert propiedades(antigua)["mag"] == 9.0


def test_magnitud_nula_es_null_y_no_cero():
    caso = unico("magnitud_nula")
    assert "mag" in propiedades(caso) and propiedades(caso)["mag"] is None
    assert b'"mag": null' in caso.valor
    contenido = evaluar(json.loads(caso.valor))
    assert contenido.magnitud is None


def test_coordenadas_invalidas_longitud_200():
    coordenadas = evento(unico("coordenadas_invalidas"))["geometry"]["coordinates"]
    assert coordenadas[0] == 200


def test_mar_en_el_atlantico_ecuatorial():
    assert evento(unico("mar"))["geometry"]["coordinates"][:2] == [-30, 0]


def test_profundidad_negativa_se_conserva():
    caso = unico("profundidad_negativa")
    assert evento(caso)["geometry"]["coordinates"][2] == -2
    assert evaluar(json.loads(caso.valor)).profundidad == -2


def test_ids_distintos_entre_casos_independientes():
    ids = {caso.clave for caso in construir()}
    assert ids == {
        b"synthetic-caso-nuevo", b"synthetic-caso-revision", b"synthetic-caso-magnitud-nula",
        b"synthetic-caso-coordenadas-invalidas", b"synthetic-caso-mar", b"synthetic-caso-profundidad-negativa",
    }


def test_la_ingesta_se_escribe_en_utc_con_milisegundos():
    assert json.loads(unico("nuevo").valor)["ingested_at"] == iso_utc(INGESTA)


# --- seleccionar -----------------------------------------------------------


def test_seleccionar_sin_nombres_devuelve_todo_en_orden():
    casos = construir()
    assert c.seleccionar(casos, None) == casos
    assert c.seleccionar(casos, []) == casos


def test_seleccionar_conserva_el_orden_de_publicacion():
    casos = construir()
    elegidos = c.seleccionar(casos, ["mar", "nuevo"])
    assert [caso.nombre for caso in elegidos] == ["nuevo", "mar"]


def test_seleccionar_un_caso_con_varios_mensajes_los_trae_todos():
    assert len(c.seleccionar(construir(), ["revision"])) == 2


def test_seleccionar_nombre_desconocido_es_error_con_el_nombre():
    with pytest.raises(ValueError, match="inexistente"):
        c.seleccionar(construir(), ["nuevo", "inexistente"])


# --- línea de órdenes ------------------------------------------------------


def test_argumentos_por_defecto():
    args = c.leer_argumentos([])
    assert args.listar is False and args.solo is None and args.base is None


def test_argumentos_solo_acepta_varios_nombres():
    assert c.leer_argumentos(["--solo", "nuevo", "mar"]).solo == ["nuevo", "mar"]


def test_argumento_base_se_lee_como_utc():
    args = c.leer_argumentos(["--base", "2026-11-08T14:00:00Z"])
    assert args.base == BASE
    args = c.leer_argumentos(["--base", "2026-11-08T15:00:00+01:00"])
    assert args.base == BASE


@pytest.mark.parametrize("texto", ["2026-11-08T14:00:00", "ayer", ""])
def test_argumento_base_sin_zona_o_mal_formado_es_error(texto):
    with pytest.raises(SystemExit):
        c.leer_argumentos(["--base", texto])


def test_listar_describe_cada_caso_sin_kafka(capsys):
    assert c.main(["--listar"]) == 0
    salida = capsys.readouterr().out
    for nombre in c.NOMBRES:
        assert nombre in salida
    assert "synthetic-caso-" in salida


def test_main_rechaza_un_caso_desconocido_sin_publicar(capsys):
    assert c.main(["--solo", "inexistente", "--listar"]) == 2
    assert "inexistente" in capsys.readouterr().err
