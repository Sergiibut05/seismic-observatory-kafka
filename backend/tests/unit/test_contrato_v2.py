"""Contrato v2: evento fusionado en `eventos.live` (specs/013-multifuente/contracts/mensajes-kafka.md)."""

import json
from datetime import datetime, timezone

import pytest

from observatorio.common.contrato import (
    SCHEMA_VERSION_FUSION,
    MensajeValido,
    Rechazo,
    construir_mensaje_v2,
    validar_mensaje,
)

INGESTA = datetime(2026, 11, 14, 10, 0, 5, tzinfo=timezone.utc)


def evento(event_id="us7000abcd", updated=1_794_471_012_345):
    return {
        "type": "Feature",
        "id": event_id,
        "geometry": {"type": "Point", "coordinates": [13.07, 42.34, 9.8]},
        "properties": {
            "time": 1_794_470_946_480,
            "updated": updated,
            "mag": 4.3,
            "magType": "mw",
            "place": "CENTRAL ITALY",
            "type": "earthquake",
        },
    }


def fuentes():
    return [
        {"fuente": "usgs", "id": "us7000abcd", "updated": 1_794_471_000_000, "principal": False, "original": {"id": "us7000abcd"}},
        {"fuente": "emsc", "id": "20261114_0000123", "updated": 1_794_471_012_345, "principal": True, "original": {"id": "20261114_0000123"}},
    ]


def construir(source="emsc", lista=None, ev=None):
    return construir_mensaje_v2(ev or evento(), fuentes() if lista is None else lista, source, INGESTA)


def validar(clave_valor, modo="live"):
    clave, valor = clave_valor
    return validar_mensaje(clave, valor, modo)


def mutar(cambio):
    clave, valor = construir()
    mensaje = json.loads(valor)
    cambio(mensaje)
    return clave, json.dumps(mensaje).encode()


def motivo(resultado):
    assert isinstance(resultado, Rechazo), resultado
    return resultado.motivo


def test_un_v2_bien_formado_es_valido_y_trae_sus_fuentes_ordenadas():
    resultado = validar(construir())
    assert isinstance(resultado, MensajeValido)
    assert resultado.event_id == "us7000abcd"
    assert resultado.source == "emsc"
    assert resultado.fuentes == ("emsc", "usgs")
    assert resultado.updated_ms == 1_794_471_012_345
    assert resultado.mensaje["schema_version"] == SCHEMA_VERSION_FUSION


def test_es_determinista_aunque_las_fuentes_lleguen_en_otro_orden():
    a = construir(lista=fuentes())
    b = construir(lista=list(reversed(fuentes())))
    assert a == b
    assert b"\n" not in a[1] and b": " not in a[1]


def test_la_clave_es_el_id_canonico():
    clave, _ = construir(ev=evento("emsc-20261114_0000123"))
    assert clave == b"emsc-20261114_0000123"


def test_v2_solo_en_live():
    # Un v2 (siempre `live`) que aparece en el topic de reproducción no corresponde a ese topic.
    assert motivo(validar(construir(), modo="replay")) == "mode_no_corresponde_al_topic"
    # Y un v2 que dijera `replay` es un modo inválido para v2.
    assert motivo(validar(mutar(lambda m: m.__setitem__("mode", "replay")), modo="replay")) == "mode_invalido"


def test_v2_sin_fuentes_es_un_campo_ausente_y_v1_con_fuentes_un_campo_desconocido():
    resultado = validar(mutar(lambda m: m.pop("fuentes")))
    assert motivo(resultado) == "campo_ausente" and "fuentes" in resultado.detalle
    resultado = validar(mutar(lambda m: m.__setitem__("schema_version", 1)))
    assert motivo(resultado) == "campo_ausente" and "campo desconocido fuentes" in resultado.detalle


@pytest.mark.parametrize(
    "cambio",
    [
        lambda m: m.__setitem__("fuentes", []),
        lambda m: m.__setitem__("fuentes", "usgs"),
        lambda m: m["fuentes"][0].pop("original"),
        lambda m: m["fuentes"][0].__setitem__("extra", 1),
        lambda m: m["fuentes"][0].__setitem__("fuente", "USGS"),
        lambda m: m["fuentes"][0].__setitem__("id", ""),
        lambda m: m["fuentes"][0].__setitem__("updated", "1794471000000"),
        lambda m: m["fuentes"][0].__setitem__("updated", True),
        lambda m: m["fuentes"][0].__setitem__("principal", 1),
        lambda m: m["fuentes"][0].__setitem__("original", "texto"),
    ],
)
def test_fuentes_invalidas(cambio):
    assert motivo(validar(mutar(cambio))) == "fuentes_invalidas"


def test_fuentes_repetidas():
    def duplicar(m):
        m["fuentes"][1]["fuente"] = m["fuentes"][0]["fuente"]

    assert motivo(validar(mutar(duplicar))) == "fuentes_repetidas"


@pytest.mark.parametrize(
    "cambio",
    [
        lambda m: [f.__setitem__("principal", False) for f in m["fuentes"]],
        lambda m: [f.__setitem__("principal", True) for f in m["fuentes"]],
        lambda m: m.__setitem__("source", "usgs"),
    ],
)
def test_una_sola_principal_y_coherente_con_source(cambio):
    assert motivo(validar(mutar(cambio))) == "principal_incoherente"


def test_las_reglas_de_v1_siguen_valiendo_en_v2():
    assert motivo(validar(mutar(lambda m: m["event"]["properties"].__setitem__("updated", -1)))) == "updated_invalido"
    clave, valor = construir()
    assert motivo(validar_mensaje(b"otra", valor, "live")) == "clave_distinta_de_id"


def test_una_sola_fuente_tambien_es_un_v2_valido():
    unica = [{"fuente": "usgs", "id": "us7000abcd", "updated": 1_794_471_012_345, "principal": True, "original": {}}]
    resultado = validar(construir(source="usgs", lista=unica))
    assert isinstance(resultado, MensajeValido) and resultado.fuentes == ("usgs",)
