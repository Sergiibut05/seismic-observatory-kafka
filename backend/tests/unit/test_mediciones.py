"""Mediciones de la feature 007: lógica pura, sin base de datos ni mediciones largas."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from observatorio import mediciones as m
from observatorio.common.catalogo import construir_indice

CUADRADO = {"type": "Polygon", "coordinates": [[[0, 0], [60, 0], [60, 60], [0, 60], [0, 0]]]}
PEQUENO = {"type": "Polygon", "coordinates": [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]]}
OTRO = {"type": "Polygon", "coordinates": [[[-100, -40], [-40, -40], [-40, 10], [-100, 10], [-100, -40]]]}
CATALOGO_REAL = Path("/catalogo/paises.geojson")


def _entidad(codigo, geometria):
    return {"type": "Feature", "properties": {"ADM0_A3": codigo, "NAME_ES": codigo}, "geometry": geometria}


@pytest.fixture
def indice_pequeno(tmp_path):
    ruta = tmp_path / "paises.geojson"
    entidades = [_entidad("GRA", CUADRADO), _entidad("PEQ", PEQUENO), _entidad("OTR", OTRO)]
    ruta.write_text(json.dumps({"type": "FeatureCollection", "features": entidades}), encoding="utf-8")
    return construir_indice(ruta)


# --- estadístico y argumentos -------------------------------------------------


def test_mediana_y_maximo_de_las_repeticiones():
    assert m.estadistica([5.0, 1.0, 3.0]) == (3.0, 5.0)
    assert m.estadistica([4.0, 2.0, 8.0, 6.0]) == (5.0, 8.0)
    assert m.estadistica([7.0]) == (7.0, 7.0)


def test_estadistica_sin_muestras_es_un_error():
    with pytest.raises(ValueError):
        m.estadistica([])


def test_tamanos_se_leen_ordenados_y_se_rechazan_los_invalidos():
    assert m.parsear_tamanos("10000, 1000,100000") == (1000, 10000, 100000)
    for malo in ("", "0", "-5", "mil", "1000,1000"):
        with pytest.raises(ValueError):
            m.parsear_tamanos(malo)


def test_medir_devuelve_una_muestra_por_repeticion_y_el_ultimo_valor():
    llamadas = []

    def trabajo():
        llamadas.append(1)
        return len(llamadas)

    resultado = m.medir(trabajo, repeticiones=3)
    assert len(resultado.muestras_ms) == 3
    assert all(muestra >= 0 for muestra in resultado.muestras_ms)
    assert resultado.valor == 3
    assert resultado.pico_kib >= 0
    # La pasada de memoria es aparte y no cambia el número de repeticiones medidas.
    assert len(llamadas) == 4


# --- búsqueda de versión: lista frente a dict ---------------------------------


def test_lista_y_dict_devuelven_la_misma_ultima_version():
    versiones = m.generar_versiones(400)
    indice = m.construir_indice_versiones(versiones)
    ids = m.ids_de_busqueda(versiones, 50)
    assert len(ids) == 50
    for event_id in ids:
        assert m.ultima_version_lista(versiones, event_id) == indice[event_id]


def test_cada_evento_tiene_dos_versiones_y_gana_la_mas_reciente():
    versiones = m.generar_versiones(10)
    assert len(versiones) == 10
    por_id: dict[str, list[int]] = {}
    for event_id, updated in versiones:
        por_id.setdefault(event_id, []).append(updated)
    assert len(por_id) == 5
    assert all(len(lista) == 2 for lista in por_id.values())
    indice = m.construir_indice_versiones(versiones)
    assert all(indice[event_id] == max(lista) for event_id, lista in por_id.items())


def test_los_datos_son_sinteticos_marcados_y_reproducibles():
    primera = m.generar_versiones(100)
    assert primera == m.generar_versiones(100)
    assert all(event_id.startswith("synthetic-medicion-") for event_id, _ in primera)
    assert m.generar_puntos(50) == m.generar_puntos(50)
    assert m.generar_instantes(50) == m.generar_instantes(50)
    assert m.generar_puntos(50) != m.generar_puntos(50, semilla=1)


# --- país: secuencial frente a STRtree ----------------------------------------


def test_secuencial_y_strtree_asignan_el_mismo_pais_en_200_puntos(indice_pequeno):
    puntos = m.generar_puntos(200)
    secuencial = m.asignar_secuencial(m.preparar_secuencial(indice_pequeno), indice_pequeno, puntos)
    con_arbol = m.asignar_con_arbol(indice_pequeno, puntos)
    assert secuencial == con_arbol
    assert len(secuencial) == 200


def test_el_secuencial_elige_como_el_arbol_el_poligono_menor_y_conserva_sin_pais(indice_pequeno):
    puntos = [(15.0, 15.0), (50.0, 50.0), (-60.0, -10.0), (170.0, 80.0)]
    secuencial = m.asignar_secuencial(m.preparar_secuencial(indice_pequeno), indice_pequeno, puntos)
    assert secuencial == [("PEQ", "PEQ"), ("GRA", "GRA"), ("OTR", "OTR"), (None, "Sin país asignado")]
    assert secuencial == m.asignar_con_arbol(indice_pequeno, puntos)


@pytest.mark.skipif(not CATALOGO_REAL.is_file(), reason="el catálogo real solo está montado en Compose")
def test_secuencial_y_strtree_coinciden_con_el_catalogo_real_en_200_puntos():
    indice = construir_indice(CATALOGO_REAL)
    puntos = m.generar_puntos(200)
    assert m.asignar_secuencial(m.preparar_secuencial(indice), indice, puntos) == m.asignar_con_arbol(indice, puntos)


# --- agregación horaria -------------------------------------------------------


def test_agregar_con_dict_y_ordenando_dan_los_mismos_recuentos_por_hora():
    instantes = m.generar_instantes(5000)
    con_dict = m.agregar_con_dict(instantes)
    ordenando = m.agregar_ordenando(instantes)
    assert con_dict == ordenando
    assert sum(con_dict.values()) == 5000
    assert all(hora % m.HORA_MS == 0 for hora in con_dict)


def test_la_hora_es_utc_por_truncamiento_del_epoch():
    una_y_media = datetime(2026, 10, 1, 1, 30, tzinfo=timezone.utc)
    ms = int(una_y_media.timestamp() * 1000)
    assert m.agregar_con_dict([ms, ms + 1000]) == {int(datetime(2026, 10, 1, 1, tzinfo=timezone.utc).timestamp() * 1000): 2}


# --- PostgreSQL: solo el esquema medicion -------------------------------------


def test_toda_sentencia_de_escritura_menciona_medicion():
    sentencias = m.sentencias_de_escritura(1000)
    assert len(sentencias) >= 6
    for sentencia in sentencias:
        assert re.search(r"\bmedicion\b", sentencia), sentencia
        assert not re.search(r"\b(live|replay|historico|ingesta)\s*\.", sentencia), sentencia


def test_la_guarda_rechaza_escribir_fuera_del_esquema_medicion():
    m.validar_escritura("DROP SCHEMA IF EXISTS medicion CASCADE")
    for fuera in (
        "INSERT INTO live.evento_actual VALUES (1)",
        "DELETE FROM replay.evento_actual",
        "DROP SCHEMA medicion CASCADE; DELETE FROM live.evento_actual",
        "UPDATE medicion.evento SET x = 1 FROM live.evento_actual",
        "TRUNCATE ingesta.cuarentena",
    ):
        with pytest.raises(ValueError):
            m.validar_escritura(fuera)


def test_las_filas_sinteticas_llevan_el_prefijo_y_sintetico_true():
    insercion = next(s for s in m.sentencias_de_escritura(1000) if s.startswith("INSERT INTO medicion.evento"))
    assert "'synthetic-medicion-'" in insercion
    assert "true" in insercion.lower()
    assert "generate_series(1, 1000)" in insercion


def test_se_leen_tiempo_y_buffers_del_explain():
    plan = [
        "Limit  (cost=1.00..2.00 rows=100 width=40) (actual time=0.010..0.020 rows=100 loops=1)",
        "  Buffers: shared hit=3 read=2",
        "  ->  Seq Scan on evento  (cost=0.00..1.00 rows=1 width=1) (actual time=0.001..0.002 rows=1 loops=1)",
        "        Buffers: shared hit=9",
        "Planning Time: 0.100 ms",
        "Execution Time: 12.345 ms",
    ]
    assert m.tiempo_de_ejecucion_ms(plan) == 12.345
    assert m.buffers_del_plan(plan) == "shared hit=3 read=2"
    assert m.buffers_del_plan(["Seq Scan on x", "Execution Time: 1.0 ms"]) == "sin datos"
    with pytest.raises(ValueError):
        m.tiempo_de_ejecucion_ms(["Seq Scan on x"])


# --- recuentos antes y después ------------------------------------------------


def _recuentos(**cambios):
    base = {
        "live.evento_actual (reales)": 100,
        "live.versiones_evento (reales)": 120,
        "live.* con prefijo synthetic-medicion-": 0,
        "replay.evento_actual (reales)": 40,
        "replay.versiones_evento (reales)": 41,
        "historico.evento_2025": 18302,
    }
    base.update({clave.replace("__", " "): valor for clave, valor in cambios.items()})
    return base


def test_los_recuentos_iguales_cumplen_la_garantia():
    assert m.comparar_recuentos(_recuentos(), _recuentos()) == []
    assert m.comparar_recuentos(_recuentos(), _recuentos(), estricto=True) == []


def test_live_puede_crecer_por_la_ingesta_pero_no_decrecer():
    # El productor sigue consultando USGS cada 60 s durante la medición.
    crecido = {"live.evento_actual (reales)": 103, "live.versiones_evento (reales)": 125}
    assert m.comparar_recuentos(_recuentos(), _recuentos() | crecido) == []
    assert m.comparar_recuentos(_recuentos(), _recuentos() | crecido, estricto=True) != []
    menos = {"live.evento_actual (reales)": 99}
    assert m.comparar_recuentos(_recuentos(), _recuentos() | menos) != []


def test_replay_historico_y_prefijo_de_medicion_no_admiten_cambios():
    for clave, valor in (
        ("replay.evento_actual (reales)", 41),
        ("replay.versiones_evento (reales)", 40),
        ("historico.evento_2025", 18303),
        ("live.* con prefijo synthetic-medicion-", 1),
    ):
        fallos = m.comparar_recuentos(_recuentos(), _recuentos() | {clave: valor})
        assert fallos, clave
        assert clave in fallos[0]


def test_un_recuento_distinto_termina_con_codigo_1_y_lo_dice():
    lecturas = iter([_recuentos(), _recuentos() | {"historico.evento_2025": 18000}])
    ejecutado = []
    garantia = m.ejecutar_con_garantia(lambda: next(lecturas), lambda: ejecutado.append(1) or "resultado")
    assert ejecutado == [1]
    assert garantia.codigo_salida == 1
    assert not garantia.cumplida
    assert "historico.evento_2025" in garantia.fallos[0]
    assert garantia.resultado == "resultado"


def test_recuentos_iguales_terminan_con_codigo_0():
    garantia = m.ejecutar_con_garantia(_recuentos, lambda: "ok")
    assert garantia.codigo_salida == 0
    assert garantia.cumplida
    assert garantia.fallos == []


def test_si_el_trabajo_falla_se_leen_los_recuentos_igualmente_y_sale_con_1():
    lecturas = []

    def leer():
        lecturas.append(1)
        return _recuentos()

    def roto():
        raise RuntimeError("falla")

    garantia = m.ejecutar_con_garantia(leer, roto)
    assert len(lecturas) == 2
    assert garantia.codigo_salida == 1
    assert garantia.resultado is None
    assert "RuntimeError" in garantia.error


# --- extrapolación ------------------------------------------------------------


def test_la_extrapolacion_lineal_y_logaritmica_se_calculan_desde_lo_medido():
    assert m.extrapolar_lineal(2.0, 1000, 100_000_000) == pytest.approx(200_000.0)
    assert m.extrapolar_constante(0.5) == 0.5
    assert m.extrapolar_logaritmico(1.0, 1000, 1_000_000) == pytest.approx(2.0)
    assert m.extrapolar_n_log_n(1.0, 1000, 1_000_000) == pytest.approx(2000.0)
    # 2.048 KiB por elemento (2048 KiB / 1.000) × 10^8 elementos, en bytes.
    assert m.extrapolar_bytes(2048, 1000, 100_000_000) == pytest.approx(2048 * 1024 / 1000 * 100_000_000)
    assert m.extrapolar_bytes(1, 1, 1) == 1024


# --- informe ------------------------------------------------------------------


def _informe():
    medidas = [
        m.Medida("version", "lista: 200 búsquedas", 1000, 5, 1.234, 2.5, 3.0),
        m.Medida("pais", "secuencial", 1000, 1, 10.0, 10.0, 4.0, nota="una repetición"),
    ]
    postgres = [
        m.PruebaPostgres(
            tamano=1000,
            consulta="busqueda",
            con_indice=False,
            mediana_ms=0.5,
            maximo_ms=0.9,
            buffers="shared hit=8",
            plan=["Seq Scan on medicion.evento", "Execution Time: 0.5 ms"],
        )
    ]
    tamanos = [m.TamanoRelacion(1000, 100_000, 100_000, 0, 200_000, 40_000, 90_000)]
    return m.Informe(
        fecha=datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc),
        comando="python -m observatorio.mediciones --tamanos 1000",
        equipo={"CPU": "Prueba 3 GHz", "Núcleos": "4", "RAM": "8 GiB"},
        tamanos=(1000,),
        repeticiones=5,
        medidas=medidas,
        coinciden_pais=True,
        postgres=postgres,
        relaciones=tamanos,
        recuentos_antes=_recuentos(),
        recuentos_despues=_recuentos(),
        fallos=[],
        esquema_residual=0,
        extrapolaciones=[],
    )


def test_el_markdown_lleva_fecha_utc_equipo_y_marca_lo_sintetico():
    texto = m.renderizar(_informe())
    assert "2026-11-08T15:00:00Z" in texto
    assert "Prueba 3 GHz" in texto
    assert "SINTÉTICO" in texto
    assert "synthetic-medicion-" in texto
    assert "Execution Time: 0.5 ms" in texto
    assert "mediana" in texto.lower() and "máximo" in texto.lower()
    assert "1,234" in texto  # decimales con coma, como en la memoria


def test_el_markdown_declara_el_incumplimiento_de_la_garantia():
    informe = _informe()
    informe.fallos = ["historico.evento_2025: antes=1 después=2"]
    texto = m.renderizar(informe)
    assert "GARANTÍA NO CUMPLIDA" in texto
    assert "historico.evento_2025: antes=1 después=2" in texto


def test_el_markdown_sin_base_dice_que_no_midio_postgresql():
    informe = _informe()
    informe.postgres = None
    informe.relaciones = None
    texto = m.renderizar(informe)
    assert "no se midió PostgreSQL" in texto


def test_las_extrapolaciones_se_rotulan_como_tales():
    informe = _informe()
    informe.extrapolaciones = [m.Extrapolacion("lista", "lineal", "10 s")]
    texto = m.renderizar(informe)
    assert "EXTRAPOLACIÓN" in texto
    assert "no medida" in texto.lower()


def test_formato_espanol_de_numeros():
    assert m.fmt(1234.5678, 2) == "1.234,57"
    assert m.fmt(0.5, 3) == "0,500"
    assert m.fmt(1000000, 0) == "1.000.000"
