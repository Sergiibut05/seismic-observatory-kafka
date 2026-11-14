"""Emparejamiento de informes entre fuentes (FR-004 a FR-008 de specs/013-multifuente)."""

import json
from datetime import datetime, timedelta, timezone

from observatorio.common.contrato import MensajeValido, validar_mensaje
from observatorio.fusion.emparejar import (
    DISTANCIA_KM,
    VENTANA_MS,
    Canonico,
    distancia_km,
    en_europa,
    fusionar,
)
from observatorio.fusion.normalizar import Informe

T0 = 1_794_470_000_000
INGESTA = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def inf(fuente, id_origen, t=T0, lat=-21.0, lon=-69.0, updated=None, mag=4.5, ingesta=INGESTA):
    return Informe(
        fuente=fuente,
        id_origen=id_origen,
        updated_ms=updated if updated is not None else t + 60_000,
        tiempo_ms=t,
        latitud=lat,
        longitud=lon,
        profundidad=10.0,
        magnitud=mag,
        tipo_magnitud="mb",
        lugar=f"lugar {fuente}",
        ingested_at=ingesta,
        original={"id": id_origen, "fuente": fuente},
    )


def km_al_norte(lat, km):
    return lat + km / 111.195


def mensajes(resultado):
    return [json.loads(valor) for _, valor in resultado.mensajes]


def aplicar(estado, canonicos, resultado):
    """Simula guardar el resultado (lo que hace `estado.guardar`)."""
    por_clave = {(i.fuente, i.id_origen): (i, c) for i, c in estado}
    for informe, canonico in resultado.informes:
        por_clave[(informe.fuente, informe.id_origen)] = (informe, canonico)
    nuevos = dict(canonicos)
    for c in resultado.canonicos:
        nuevos[c.id] = c
    return list(por_clave.values()), nuevos


def test_misma_hora_y_lugar_de_dos_fuentes_es_un_solo_evento():
    r = fusionar([inf("usgs", "us1"), inf("emsc", "e1", t=T0 + 3_000)], [], {})
    assert r.resumen["fusionados"] == 1
    (m,) = mensajes(r)
    assert m["event"]["id"] == "us1"
    assert [f["fuente"] for f in m["fuentes"]] == ["emsc", "usgs"]
    assert {i.id_origen: c for i, c in r.informes} == {"us1": "us1", "e1": "us1"}


def test_fuera_de_la_ventana_de_tiempo_o_de_distancia_son_dos_eventos():
    lejos_t = fusionar([inf("usgs", "us1"), inf("emsc", "e1", t=T0 + VENTANA_MS + 1)], [], {})
    lejos_d = fusionar([inf("usgs", "us1"), inf("emsc", "e1", lat=km_al_norte(-21.0, DISTANCIA_KM + 5))], [], {})
    for r in (lejos_t, lejos_d):
        assert sorted(m["event"]["id"] for m in mensajes(r)) == ["emsc-e1", "us1"]


def test_en_el_borde_de_la_ventana_si_se_fusiona():
    r = fusionar([inf("usgs", "us1"), inf("emsc", "e1", t=T0 + VENTANA_MS, lat=km_al_norte(-21.0, 99))], [], {})
    assert len(r.mensajes) == 1


def test_dos_informes_de_la_misma_fuente_nunca_se_fusionan():
    # Una réplica 5 s después y a 2 km: misma fuente, dos terremotos.
    r = fusionar([inf("usgs", "us1"), inf("usgs", "us2", t=T0 + 5_000, lat=km_al_norte(-21.0, 2))], [], {})
    assert sorted(m["event"]["id"] for m in mensajes(r)) == ["us1", "us2"]


def test_con_dos_candidatos_gana_el_mas_parecido_y_cada_evento_un_informe_por_fuente():
    principal = inf("usgs", "us1")
    replica = inf("usgs", "us2", t=T0 + 20_000, lat=km_al_norte(-21.0, 3))
    # EMSC ve la réplica: más cerca en tiempo de us2 que de us1.
    emsc_replica = inf("emsc", "e2", t=T0 + 19_000, lat=km_al_norte(-21.0, 4))
    emsc_principal = inf("emsc", "e1", t=T0 + 1_000)
    r = fusionar([principal, replica, emsc_replica, emsc_principal], [], {})
    evento = {i.id_origen: c for i, c in r.informes}
    assert evento == {"us1": "us1", "e1": "us1", "us2": "us2", "e2": "us2"}


def test_el_id_es_estable_cuando_llega_la_segunda_fuente():
    r1 = fusionar([inf("emsc", "e1")], [], {})
    assert mensajes(r1)[0]["event"]["id"] == "emsc-e1"
    estado, canonicos = aplicar([], {}, r1)
    r2 = fusionar([inf("usgs", "us1", t=T0 + 2_000)], estado, canonicos)
    (m,) = mensajes(r2)
    assert m["event"]["id"] == "emsc-e1"  # no pasa a us1 aunque USGS sea la principal fuera de Europa
    assert m["source"] == "usgs"
    assert [f["fuente"] for f in m["fuentes"]] == ["emsc", "usgs"]


def test_en_el_mismo_lote_el_evento_conserva_el_id_usgs_aunque_emsc_sea_anterior():
    r = fusionar([inf("emsc", "e1", t=T0), inf("usgs", "us1", t=T0 + 2_000)], [], {})
    (m,) = mensajes(r)
    assert m["event"]["id"] == "us1"


def test_principal_emsc_en_europa_y_usgs_fuera():
    italia = fusionar([inf("usgs", "us1", lat=42.3, lon=13.1, mag=4.1), inf("emsc", "e1", lat=42.35, lon=13.07, mag=4.3)], [], {})
    chile = fusionar([inf("usgs", "us2", mag=5.0), inf("emsc", "e2", mag=5.2)], [], {})
    (mi,) = mensajes(italia)
    (mc,) = mensajes(chile)
    assert mi["source"] == "emsc" and mi["event"]["properties"]["mag"] == 4.3
    assert mi["event"]["geometry"]["coordinates"][:2] == [13.07, 42.35]
    assert mc["source"] == "usgs" and mc["event"]["properties"]["mag"] == 5.0
    assert en_europa(42.3, 13.1) and not en_europa(-21.0, -69.0)


def test_una_revision_sube_la_version_y_conserva_el_evento():
    estado, canonicos = aplicar([], {}, fusionar([inf("usgs", "us1"), inf("emsc", "e1")], [], {}))
    v1 = canonicos["us1"].updated_ms
    revision = inf("emsc", "e1", updated=T0 + 120_000, mag=4.7)
    r = fusionar([revision], estado, canonicos)
    (m,) = mensajes(r)
    assert m["event"]["id"] == "us1"
    assert m["event"]["properties"]["updated"] > v1
    assert r.resumen["revisados"] == 1


def test_la_version_crece_aunque_la_nueva_fuente_sea_mas_vieja():
    # USGS ya emitido con updated alto; EMSC llega con un updated menor: la versión no puede bajar.
    estado, canonicos = aplicar([], {}, fusionar([inf("usgs", "us1", updated=T0 + 900_000)], [], {}))
    r = fusionar([inf("emsc", "e1", updated=T0 + 10_000)], estado, canonicos)
    (m,) = mensajes(r)
    assert m["event"]["properties"]["updated"] == T0 + 900_001


def test_reentrega_y_version_vieja_no_emiten_nada():
    estado, canonicos = aplicar([], {}, fusionar([inf("usgs", "us1", updated=T0 + 5_000)], [], {}))
    igual = fusionar([inf("usgs", "us1", updated=T0 + 5_000)], estado, canonicos)
    vieja = fusionar([inf("usgs", "us1", updated=T0 + 1_000)], estado, canonicos)
    for r in (igual, vieja):
        assert r.mensajes == () and r.informes == () and r.resumen["sin_cambios"] == 1


def test_determinista_aunque_cambie_el_orden_de_llegada():
    lote = [inf("usgs", "us1"), inf("emsc", "e1", t=T0 + 1_000), inf("usgs", "us9", t=T0 + 600_000)]
    a = fusionar(lote, [], {})
    b = fusionar(list(reversed(lote)), [], {})
    assert a.mensajes == b.mensajes and a.canonicos == b.canonicos


def test_la_reentrega_tras_un_fallo_produce_los_mismos_bytes():
    # Fallo entre escribir en Kafka y guardar el estado: el lote se repite con el mismo estado.
    estado, canonicos = aplicar([], {}, fusionar([inf("usgs", "us1")], [], {}))
    lote = [inf("emsc", "e1", t=T0 + 2_000)]
    assert fusionar(lote, estado, canonicos).mensajes == fusionar(lote, estado, canonicos).mensajes


def test_ingested_at_es_el_maximo_de_las_fuentes_no_la_hora_del_proceso():
    tarde = INGESTA + timedelta(minutes=7)
    (m,) = mensajes(fusionar([inf("usgs", "us1"), inf("emsc", "e1", ingesta=tarde)], [], {}))
    assert m["ingested_at"] == "2026-11-14T12:07:00.000Z"


def test_los_mensajes_cumplen_el_contrato_v2():
    r = fusionar([inf("usgs", "us1"), inf("emsc", "e1"), inf("emsc", "e2", t=T0 + 3_600_000)], [], {})
    for clave, valor in r.mensajes:
        resultado = validar_mensaje(clave, valor, "live")
        assert isinstance(resultado, MensajeValido), resultado
        assert resultado.event_id == clave.decode()


def test_un_evento_previo_sembrado_recibe_a_su_pareja_sin_duplicarse():
    # Siembra (FR-009): el evento USGS ya estaba en la base antes de la fusión.
    sembrado = inf("usgs", "us7000old", updated=T0 + 5_000)
    canonicos = {"us7000old": Canonico("us7000old", T0 + 5_000, f"usgs:us7000old:{T0 + 5_000}", "usgs")}
    r = fusionar([inf("emsc", "e1", t=T0 + 4_000)], [(sembrado, "us7000old")], canonicos)
    (m,) = mensajes(r)
    assert m["event"]["id"] == "us7000old"
    assert m["event"]["properties"]["updated"] > T0 + 5_000


def test_distancia_haversine():
    assert round(distancia_km(0, 0, 0, 1)) == 111
    assert distancia_km(42.0, 13.0, 42.0, 13.0) == 0
