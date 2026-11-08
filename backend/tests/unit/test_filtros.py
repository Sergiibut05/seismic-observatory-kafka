"""Pruebas de los filtros de la API (feature 005, FR-008): validación y WHERE parametrizado."""

from datetime import datetime, timedelta, timezone

import pytest

from observatorio.api.filtros import (
    PARAMS_COMPARACION,
    PARAMS_FILTRO,
    PARAMS_LISTA,
    Filtros,
    FiltroInvalido,
    construir_where,
    leer_filtros,
    leer_paginacion,
    leer_ventana,
    valores_unicos,
)

UTC = timezone.utc
AHORA = datetime(2026, 11, 2, 12, 34, 56, 789000, tzinfo=UTC)


def filtros(**valores):
    return leer_filtros(valores_unicos(valores.items(), PARAMS_FILTRO))


def invalido(**valores) -> str:
    with pytest.raises(FiltroInvalido) as exc:
        filtros(**valores)
    return exc.value.parametro


# --- sin filtros -----------------------------------------------------------


def test_sin_filtros_solo_reales():
    f = filtros()
    assert f == Filtros()
    assert construir_where(f) == (" WHERE NOT sintetico", [])


def test_con_incluir_sinteticos_no_hay_condicion_de_sinteticos():
    assert construir_where(filtros(incluir_sinteticos="true")) == ("", [])


# --- fechas ----------------------------------------------------------------


def test_fechas_con_z_y_con_offset_se_pasan_a_utc():
    f = filtros(desde="2026-11-02T10:00:00Z", hasta="2026-11-02T13:00:00+02:00")
    assert f.desde == datetime(2026, 11, 2, 10, tzinfo=UTC)
    assert f.hasta == datetime(2026, 11, 2, 11, tzinfo=UTC)
    assert f.desde.utcoffset() == timedelta(0)


def test_milisegundos_en_las_fechas():
    assert filtros(desde="2026-11-02T10:59:59.999Z").desde.microsecond == 999000


@pytest.mark.parametrize(
    "texto",
    ["2026-11-02T10:00:00", "2026-11-02", "ayer", "", "2026-13-01T00:00:00Z", "2026-11-02T10:00:00 01:00"],
)
def test_fecha_sin_zona_o_mal_formada_es_invalida(texto):
    assert invalido(desde=texto) == "desde"
    assert invalido(hasta=texto) == "hasta"


def test_desde_debe_ser_anterior_a_hasta():
    assert invalido(desde="2026-11-02T10:00:00Z", hasta="2026-11-02T10:00:00Z") == "hasta"
    assert invalido(desde="2026-11-02T11:00:00Z", hasta="2026-11-02T10:00:00Z") == "hasta"


def test_desde_inclusivo_y_hasta_exclusivo_en_el_sql():
    f = filtros(desde="2026-11-02T10:00:00Z", hasta="2026-11-02T11:00:00Z")
    sql, params = construir_where(f)
    assert "ocurrencia >= %s" in sql and "ocurrencia < %s" in sql
    assert params == [f.desde, f.hasta]


def test_un_desfase_extremo_no_desborda():
    assert invalido(desde="0001-01-01T00:00:00+05:00") == "desde"


# --- magnitud --------------------------------------------------------------


def test_magnitud_valida():
    f = filtros(magnitud_min="-1.5", magnitud_max="7")
    assert (f.magnitud_min, f.magnitud_max) == (-1.5, 7.0)
    sql, params = construir_where(f)
    assert "magnitud >= %s" in sql and "magnitud <= %s" in sql
    assert params == [-1.5, 7.0]


@pytest.mark.parametrize("texto", ["nan", "inf", "-inf", "1e3", "11", "-10.5", "abc", "", "1_0", " 5", "5,5", "--1"])
def test_magnitud_invalida(texto):
    assert invalido(magnitud_min=texto) == "magnitud_min"
    assert invalido(magnitud_max=texto) == "magnitud_max"


def test_los_limites_de_magnitud_se_admiten():
    f = filtros(magnitud_min="-10", magnitud_max="10")
    assert (f.magnitud_min, f.magnitud_max) == (-10.0, 10.0)


def test_magnitud_min_mayor_que_max():
    assert invalido(magnitud_min="5", magnitud_max="4") == "magnitud_max"


def test_magnitud_cero_es_un_filtro_real_no_ausente():
    sql, params = construir_where(filtros(magnitud_min="0"))
    assert "magnitud >= %s" in sql
    assert params == [0.0]


# --- país y subregión ------------------------------------------------------


def test_pais_adm0_a3():
    sql, params = construir_where(filtros(pais="USA"))
    assert "pais_codigo = %s" in sql and params == ["USA"]


def test_sin_pais_asignado_filtra_por_nulo():
    sql, params = construir_where(filtros(pais="Sin país asignado"))
    assert "pais_codigo IS NULL" in sql and params == []


@pytest.mark.parametrize("texto", ["usa", "US", "USAA", "U1A", "", "Sin pais asignado", "ESP "])
def test_pais_invalido(texto):
    assert invalido(pais=texto) == "pais"


def test_subregion_igualdad_con_la_dimension():
    sql, params = construir_where(filtros(subregion="Norteamérica"))
    assert "pais_codigo IN (SELECT sr.codigo FROM ingesta.pais sr WHERE sr.subregion = %s)" in sql
    assert params == ["Norteamérica"]


def test_subregion_sin_pais_asignado_filtra_por_nulo():
    sql, params = construir_where(filtros(subregion="Sin país asignado"))
    assert "pais_codigo IS NULL" in sql and params == []


@pytest.mark.parametrize("texto", ["", "x" * 81, "con\nsalto", "tab\taqui", "nulo\x00"])
def test_subregion_invalida(texto):
    assert invalido(subregion=texto) == "subregion"


def test_subregion_de_80_caracteres_es_valida():
    assert filtros(subregion="x" * 80).subregion == "x" * 80


def test_pais_y_subregion_se_combinan_con_y():
    sql, params = construir_where(filtros(pais="USA", subregion="Norteamérica"))
    assert " AND " in sql and "pais_codigo = %s" in sql and "sr.subregion = %s" in sql
    assert params == ["USA", "Norteamérica"]


# --- sintéticos ------------------------------------------------------------


@pytest.mark.parametrize("texto", ["True", "1", "si", "", "TRUE"])
def test_incluir_sinteticos_invalido(texto):
    assert invalido(incluir_sinteticos=texto) == "incluir_sinteticos"


def test_comparacion_y_historico_ajustan_fechas_y_sinteticos():
    f = filtros(desde="2026-11-02T10:00:00Z", pais="USA")
    sql, _ = construir_where(f, fechas=False)
    assert "ocurrencia" not in sql and "NOT sintetico" in sql
    sql, params = construir_where(f, fechas=False, sinteticos=False)
    assert sql == " WHERE pais_codigo = %s" and params == ["USA"]


# --- modo (feature 007, contrato 0.3.0) ------------------------------------


def test_modo_por_defecto_es_live():
    assert filtros().modo == "live"
    assert Filtros().modo == "live"


def test_modo_replay_se_lee_y_no_aparece_en_el_where():
    f = filtros(modo="replay")
    assert f.modo == "replay"
    assert construir_where(f) == (" WHERE NOT sintetico", [])
    sql, params = construir_where(filtros(modo="replay", pais="USA"))
    assert "replay" not in sql and params == ["USA"]


def test_modo_live_explicito_vale():
    assert filtros(modo="live").modo == "live"


@pytest.mark.parametrize("texto", ["Replay", "REPLAY", "todos", "", "LIVE", "replay ", "reproduccion", "'; DROP TABLE x;--"])
def test_modo_invalido_es_400_con_el_nombre_del_parametro(texto):
    assert invalido(modo=texto) == "modo"


def test_modo_repetido_es_invalido():
    with pytest.raises(FiltroInvalido) as exc:
        valores_unicos([("modo", "live"), ("modo", "replay")], PARAMS_FILTRO)
    assert exc.value.parametro == "modo"


def test_modo_viaja_en_los_conjuntos_de_parametros():
    assert "modo" in PARAMS_FILTRO and "modo" in PARAMS_LISTA and "modo" in PARAMS_COMPARACION
    assert valores_unicos([("modo", "replay")], PARAMS_COMPARACION) == {"modo": "replay"}


def test_la_ventana_con_ancla_termina_en_el_ancla():
    ancla = datetime(2025, 3, 1, 12, 0, 0, 1000, tzinfo=UTC)
    f = leer_ventana(Filtros(modo="replay"), AHORA, ancla)
    assert f.hasta == ancla and f.hasta - f.desde == timedelta(hours=24)
    assert f.modo == "replay"


def test_la_ventana_sin_ancla_sigue_terminando_ahora():
    assert leer_ventana(Filtros(), AHORA, None).hasta == AHORA


def test_la_ventana_explicita_ignora_el_ancla():
    desde = datetime(2025, 3, 1, tzinfo=UTC)
    hasta = datetime(2025, 3, 2, tzinfo=UTC)
    f = leer_ventana(Filtros(desde=desde, hasta=hasta), AHORA, AHORA)
    assert (f.desde, f.hasta) == (desde, hasta)


def test_la_ventana_con_solo_desde_y_ancla_llega_al_ancla():
    ancla = datetime(2025, 3, 1, 12, tzinfo=UTC)
    f = leer_ventana(Filtros(desde=ancla - timedelta(hours=5)), AHORA, ancla)
    assert f.hasta == ancla


# --- inyección SQL ---------------------------------------------------------

INTENTO = "'; DROP TABLE x;--"


def test_un_intento_de_inyeccion_viaja_en_params_y_no_en_el_sql():
    f = filtros(subregion=INTENTO)
    sql, params = construir_where(f)
    assert "DROP" not in sql and "x;--" not in sql and "'" not in sql
    assert params == [INTENTO]


@pytest.mark.parametrize("nombre", ["pais", "magnitud_min", "magnitud_max", "desde", "hasta", "incluir_sinteticos"])
def test_la_inyeccion_en_el_resto_de_parametros_se_rechaza(nombre):
    assert invalido(**{nombre: INTENTO}) == nombre


def test_el_sql_generado_solo_contiene_fragmentos_constantes():
    f = filtros(
        desde="2026-11-02T10:00:00Z",
        hasta="2026-11-02T11:00:00Z",
        magnitud_min="4",
        magnitud_max="6",
        pais="USA",
        subregion=INTENTO,
    )
    sql, params = construir_where(f)
    assert sql.count("%s") == len(params) == 6
    assert INTENTO not in sql


# --- parámetros desconocidos o repetidos -----------------------------------


def test_parametro_desconocido():
    with pytest.raises(FiltroInvalido) as exc:
        valores_unicos([("magnitud_min", "4"), ("ordenar", "magnitud")], PARAMS_FILTRO)
    assert exc.value.parametro == "ordenar"


def test_parametro_repetido():
    with pytest.raises(FiltroInvalido) as exc:
        valores_unicos([("pais", "USA"), ("pais", "ESP")], PARAMS_FILTRO)
    assert exc.value.parametro == "pais"


def test_el_nombre_de_un_parametro_raro_no_se_devuelve():
    with pytest.raises(FiltroInvalido) as exc:
        valores_unicos([("<script>", "1")], PARAMS_FILTRO)
    assert exc.value.parametro == "desconocido"


def test_cada_endpoint_admite_su_conjunto():
    assert "limite" not in PARAMS_FILTRO and "limite" in PARAMS_LISTA
    with pytest.raises(FiltroInvalido):
        valores_unicos([("desde", "2026-11-02T10:00:00Z")], PARAMS_COMPARACION)
    with pytest.raises(FiltroInvalido):
        valores_unicos([("incluir_sinteticos", "true")], PARAMS_COMPARACION)
    assert valores_unicos([("pais", "USA")], PARAMS_COMPARACION) == {"pais": "USA"}


# --- paginación ------------------------------------------------------------


def test_paginacion_por_defecto():
    assert leer_paginacion({}) == (100, 0)


def test_paginacion_en_los_limites():
    assert leer_paginacion({"limite": "1", "desplazamiento": "0"}) == (1, 0)
    assert leer_paginacion({"limite": "500", "desplazamiento": "100000"}) == (500, 100_000)


@pytest.mark.parametrize("limite", ["0", "501", "-1", "x", "", "1.5", "99999999999"])
def test_limite_invalido(limite):
    with pytest.raises(FiltroInvalido) as exc:
        leer_paginacion({"limite": limite})
    assert exc.value.parametro == "limite"


@pytest.mark.parametrize("desplazamiento", ["100001", "-1", "x", "", "1e3"])
def test_desplazamiento_invalido(desplazamiento):
    with pytest.raises(FiltroInvalido) as exc:
        leer_paginacion({"desplazamiento": desplazamiento})
    assert exc.value.parametro == "desplazamiento"


# --- ventana de horas ------------------------------------------------------


def test_ventana_por_defecto_24_horas():
    f = leer_ventana(Filtros(), AHORA)
    assert f.hasta == AHORA and f.hasta - f.desde == timedelta(hours=24)


def test_ventana_solo_desde_llega_hasta_ahora():
    f = leer_ventana(Filtros(desde=AHORA - timedelta(hours=3)), AHORA)
    assert f.hasta == AHORA


def test_ventana_solo_hasta_retrocede_24_horas():
    hasta = datetime(2026, 11, 1, tzinfo=UTC)
    assert leer_ventana(Filtros(hasta=hasta), AHORA).desde == hasta - timedelta(hours=24)


def test_ventana_de_31_dias_es_valida_y_de_mas_no():
    desde = datetime(2026, 10, 1, tzinfo=UTC)
    assert leer_ventana(Filtros(desde=desde, hasta=desde + timedelta(days=31)), AHORA).desde == desde
    with pytest.raises(FiltroInvalido) as exc:
        leer_ventana(Filtros(desde=desde, hasta=desde + timedelta(days=31, milliseconds=1)), AHORA)
    assert exc.value.parametro == "hasta"


def test_ventana_con_desde_en_el_futuro_es_invalida():
    with pytest.raises(FiltroInvalido):
        leer_ventana(Filtros(desde=AHORA + timedelta(hours=1)), AHORA)


def test_la_ventana_conserva_el_resto_de_filtros():
    f = leer_ventana(Filtros(pais="USA", magnitud_min=4.0), AHORA)
    assert f.pais == "USA" and f.magnitud_min == 4.0
