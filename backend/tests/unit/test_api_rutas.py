"""Rutas de la API sin base real ni `httpx`: se llama a la aplicación ASGI con una base falsa.

Cubre el reparto de errores (400/503/500 genéricos), CORS (AC-9), 404 de `/docs`, 405 y la forma
de cada respuesta. El SQL real, los índices y los tiempos se comprueban en vivo (T10).
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import psycopg
import pytest

from observatorio.api.main import crear_app
from observatorio.api.rutas import ejecutar
from observatorio.common.config import ajustes_api
from observatorio.common.db import SinConexion

NETLIFY = "https://observatorio-sismico.netlify.app"
LOCAL = "http://localhost:4200"
UTC = timezone.utc


def ajustes(**extra):
    return ajustes_api({"POSTGRES_PASSWORD": "x", **extra})


class BdFalsa:
    """`responder(sql, params)` devuelve las filas; guarda las consultas para inspeccionarlas."""

    def __init__(self, responder=None, error=None):
        self.responder = responder or (lambda sql, params: [(0,)] if sql.startswith("SELECT count(*)") else [])
        self.error = error
        self.llamadas: list[tuple[str, list]] = []

    async def consultar(self, sql, params=None, timeout=3.0):
        if self.error is not None:
            raise self.error
        self.llamadas.append((sql, list(params or [])))
        return self.responder(sql, params)

    async def cerrar(self):
        pass


async def _llamar(app, metodo, ruta, query="", cabeceras=None):
    cuerpo_enviado = False
    mensajes = []

    async def receive():
        nonlocal cuerpo_enviado
        if cuerpo_enviado:
            await asyncio.sleep(3600)
        cuerpo_enviado = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(mensaje):
        mensajes.append(mensaje)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": metodo,
        "scheme": "http",
        "path": ruta,
        "raw_path": ruta.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (cabeceras or {}).items()],
        "client": ("127.0.0.1", 50000),
        "server": ("api", 8000),
    }
    await app(scope, receive, send)
    inicio = next(m for m in mensajes if m["type"] == "http.response.start")
    cuerpo = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
    return inicio["status"], {k.decode(): v.decode() for k, v in inicio["headers"]}, cuerpo


def llamar(app, metodo, ruta, query="", cabeceras=None):
    return asyncio.run(_llamar(app, metodo, ruta, query, cabeceras))


def obtener(app, ruta, query=""):
    estado, cabeceras, cuerpo = llamar(app, "GET", ruta, query)
    return estado, json.loads(cuerpo)


def app_con(bd=None, **extra):
    return crear_app(ajustes(**extra), db=bd or BdFalsa())


# --- AC-9: CORS, 405 y rutas sin documentar --------------------------------


def preflight(app, origen, cabecera="ngrok-skip-browser-warning", ruta="/eventos"):
    return llamar(
        app,
        "OPTIONS",
        ruta,
        cabeceras={
            "Origin": origen,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": cabecera,
        },
    )


@pytest.mark.parametrize("origen", [NETLIFY, LOCAL])
def test_preflight_de_los_origenes_permitidos(origen):
    app = app_con(CORS_ORIGEN_NETLIFY=NETLIFY)
    estado, cabeceras, _ = preflight(app, origen)
    assert 200 <= estado < 300
    assert cabeceras["access-control-allow-origin"] == origen
    assert "ngrok-skip-browser-warning" in cabeceras["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in cabeceras
    assert cabeceras["access-control-allow-origin"] != "*"
    metodos = {m.strip() for m in cabeceras["access-control-allow-methods"].split(",")}
    assert metodos == {"GET", "OPTIONS"}


def test_otro_origen_no_recibe_cabeceras_cors():
    app = app_con(CORS_ORIGEN_NETLIFY=NETLIFY)
    for origen in ("https://malo.example.com", "http://localhost:4201", NETLIFY.replace("https", "http")):
        _, cabeceras, _ = preflight(app, origen)
        assert not [k for k in cabeceras if k.startswith("access-control-allow")], origen


def test_una_cabecera_no_permitida_se_rechaza_en_el_preflight():
    app = app_con(CORS_ORIGEN_NETLIFY=NETLIFY)
    estado, _, cuerpo = preflight(app, NETLIFY, cabecera="authorization")
    assert estado == 400 and b"Disallowed CORS headers" in cuerpo


def test_sin_origen_netlify_solo_pasa_localhost():
    app = app_con()
    assert preflight(app, LOCAL)[1]["access-control-allow-origin"] == LOCAL
    assert "access-control-allow-origin" not in preflight(app, NETLIFY)[1]


def test_get_con_origen_permitido_lleva_la_cabecera():
    app = app_con(CORS_ORIGEN_NETLIFY=NETLIFY)
    _, cabeceras, _ = llamar(app, "GET", "/recuentos/pais", cabeceras={"Origin": NETLIFY})
    assert cabeceras["access-control-allow-origin"] == NETLIFY
    _, cabeceras, _ = llamar(app, "GET", "/recuentos/pais", cabeceras={"Origin": "https://malo.example.com"})
    assert "access-control-allow-origin" not in cabeceras


def test_los_errores_tambien_llevan_cors():
    app = app_con(BdFalsa(error=SinConexion("x")), CORS_ORIGEN_NETLIFY=NETLIFY)
    estado, cabeceras, _ = llamar(app, "GET", "/eventos", cabeceras={"Origin": NETLIFY})
    assert estado == 503 and cabeceras["access-control-allow-origin"] == NETLIFY
    estado, cabeceras, _ = llamar(app, "GET", "/eventos", "pais=x", cabeceras={"Origin": NETLIFY})
    assert estado == 400 and cabeceras["access-control-allow-origin"] == NETLIFY


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("ruta", ["/eventos", "/eventos/mapa", "/status", "/comparacion-historica", "/recuentos/hora"])
def test_solo_get_y_options_otros_metodos_dan_405(metodo, ruta):
    assert llamar(app_con(), metodo, ruta)[0] == 405


@pytest.mark.parametrize("ruta", ["/docs", "/redoc", "/openapi.json", "/admin", "/eventos/x"])
def test_sin_documentacion_ni_administracion(ruta):
    assert llamar(app_con(), "GET", ruta)[0] == 404


# --- errores genéricos -----------------------------------------------------


def test_400_con_el_nombre_del_parametro_y_sin_el_valor():
    estado, datos = obtener(app_con(), "/eventos", "magnitud_min=abc")
    assert estado == 400
    assert datos == {"error": "parametro_invalido", "parametro": "magnitud_min"}


def test_parametros_desconocidos_o_repetidos_son_400():
    app = app_con()
    assert obtener(app, "/eventos", "color=rojo")[1]["parametro"] == "color"
    assert obtener(app, "/eventos/mapa", "pais=USA&pais=ESP")[1]["parametro"] == "pais"
    assert obtener(app, "/eventos/mapa", "limite=5")[0] == 400  # `limite` solo vale en /eventos
    assert obtener(app, "/comparacion-historica", "desde=2026-11-02T00:00:00Z")[0] == 400


def test_la_inyeccion_en_la_consulta_es_400_sin_llegar_a_la_base():
    bd = BdFalsa()
    estado, datos = obtener(app_con(bd), "/recuentos/pais", "pais=%27%3B%20DROP%20TABLE%20x%3B--")
    assert estado == 400 and datos["parametro"] == "pais"
    assert bd.llamadas == []


def test_503_sin_conexion_cuerpo_generico_nunca_lista_vacia():
    app = app_con(BdFalsa(error=SinConexion("sin conexión con PostgreSQL")))
    for ruta in (
        "/eventos", "/eventos/mapa", "/recuentos/pais", "/recuentos/subregion", "/recuentos/hora",
        "/distribuciones/magnitud", "/distribuciones/profundidad", "/comparacion-historica",
    ):
        estado, datos = obtener(app, ruta)
        assert estado == 503, ruta
        assert datos == {"error": "servicio_no_disponible"}, ruta


def test_503_ante_un_error_de_psycopg_sin_detalles():
    app = app_con(BdFalsa(error=psycopg.errors.UndefinedTable('no existe la relación "historico.x"')))
    estado, cuerpo = llamar(app, "GET", "/eventos")[0], llamar(app, "GET", "/eventos")[2]
    assert estado == 503
    assert b"historico" not in cuerpo and b"relaci" not in cuerpo


def test_503_ante_un_timeout():
    assert obtener(app_con(BdFalsa(error=TimeoutError())), "/eventos")[0] == 503


def test_500_generico_sin_traza(caplog):
    def estalla(sql, params):
        raise RuntimeError("secreto interno /app/observatorio/x.py")

    with caplog.at_level(logging.ERROR):
        estado, cabeceras, cuerpo = llamar(app_con(BdFalsa(estalla)), "GET", "/eventos")
    assert estado == 500
    assert json.loads(cuerpo) == {"error": "error_interno"}
    assert b"secreto" not in cuerpo and b"Traceback" not in cuerpo


def test_500_tambien_lleva_cors():
    def estalla(sql, params):
        raise RuntimeError("x")

    app = app_con(BdFalsa(estalla), CORS_ORIGEN_NETLIFY=NETLIFY)
    estado, cabeceras, _ = llamar(app, "GET", "/eventos", cabeceras={"Origin": NETLIFY})
    assert estado == 500 and cabeceras["access-control-allow-origin"] == NETLIFY


def test_ejecutar_traduce_los_fallos_de_la_base():
    for error in (SinConexion("x"), psycopg.OperationalError("x"), TimeoutError(), OSError("x")):
        with pytest.raises(Exception) as exc:
            asyncio.run(ejecutar(BdFalsa(error=error), "SELECT 1"))
        assert type(exc.value).__name__ == "ServicioNoDisponible"


def test_ejecutar_deja_pasar_un_error_de_programacion():
    with pytest.raises(RuntimeError):
        asyncio.run(ejecutar(BdFalsa(error=RuntimeError("bug")), "SELECT 1"))


# --- /eventos --------------------------------------------------------------

FILA_LISTA = (
    "us7000abcd",
    datetime(2026, 11, 2, 10, 0, 0, 123000, tzinfo=UTC),
    datetime(2026, 11, 2, 10, 5, tzinfo=UTC),
    None,
    12.5,
    -122.5,
    37.25,
    None,
    "Sin país asignado",
    None,
    False,
)


def test_lista_con_total_paginacion_y_nulos():
    def responder(sql, params):
        return [(1234,)] if sql.startswith("SELECT count(*)") else [FILA_LISTA]

    bd = BdFalsa(responder)
    estado, datos = obtener(app_con(bd), "/eventos", "limite=10&desplazamiento=20&pais=Sin%20pa%C3%ADs%20asignado")
    assert estado == 200
    assert (datos["total"], datos["limite"], datos["desplazamiento"]) == (1234, 10, 20)
    evento = datos["eventos"][0]
    assert evento["magnitud"] is None and evento["pais_codigo"] is None and evento["subregion"] is None
    assert evento["ocurrencia"] == "2026-11-02T10:00:00.123Z"
    assert evento["pais_nombre"] == "Sin país asignado" and evento["sintetico"] is False
    assert bd.llamadas[1][1][-2:] == [10, 20]
    assert "pais_codigo IS NULL" in bd.llamadas[0][0]


def test_valores_del_usuario_viajan_como_parametros():
    bd = BdFalsa()
    obtener(app_con(bd), "/eventos", "subregion=%27%3B%20DROP%20TABLE%20x%3B--")
    for consulta, params in bd.llamadas:
        assert "DROP" not in consulta
        assert "'; DROP TABLE x;--" in params


def test_lista_por_defecto_100_y_solo_reales():
    bd = BdFalsa()
    estado, datos = obtener(app_con(bd), "/eventos")
    assert estado == 200 and datos["eventos"] == [] and datos["limite"] == 100
    assert "NOT sintetico" in bd.llamadas[0][0]


# --- /eventos/mapa ---------------------------------------------------------


def test_mapa_geojson_con_tope_y_truncado():
    fila = ("us1", datetime(2026, 11, 2, tzinfo=UTC), datetime(2026, 11, 2, tzinfo=UTC), 4.5, None, 1.0, 2.0, "X", False)

    def responder(sql, params):
        return [(9999,)] if sql.startswith("SELECT count(*)") else [fila]

    estado, datos = obtener(app_con(BdFalsa(responder)), "/eventos/mapa")
    assert estado == 200 and datos["type"] == "FeatureCollection"
    assert datos["total"] == 9999 and datos["limite"] == 5000 and datos["truncado"] is True
    assert datos["features"][0]["geometry"]["coordinates"] == [1.0, 2.0]
    assert datos["features"][0]["properties"]["profundidad"] is None


# --- recuentos y distribuciones --------------------------------------------


def test_recuentos_por_pais_incluyen_sin_pais_asignado():
    filas = [("USA", "Estados Unidos", 196), (None, "Sin país asignado", 48)]
    estado, datos = obtener(app_con(BdFalsa(lambda s, p: filas)), "/recuentos/pais")
    assert estado == 200 and datos["total"] == 244
    assert datos["categorias"][1] == {"codigo": None, "nombre": "Sin país asignado", "recuento": 48}


def test_recuentos_por_subregion_distinguen_sin_pais():
    filas = [("Norteamérica", False, 196), (None, True, 48), ("Caribe", False, 2)]
    _, datos = obtener(app_con(BdFalsa(lambda s, p: filas)), "/recuentos/subregion")
    assert datos["total"] == 246
    assert {"nombre": "Sin país asignado", "recuento": 48} in datos["categorias"]
    assert [c["nombre"] for c in datos["categorias"]] == ["Norteamérica", "Sin país asignado", "Caribe"]


def test_recuentos_por_hora_con_ceros_y_ventana_declarada():
    filas = [(datetime(2026, 11, 2, 7, tzinfo=UTC), 2), (datetime(2026, 11, 2, 9, tzinfo=UTC), 1)]
    estado, datos = obtener(
        app_con(BdFalsa(lambda s, p: filas)),
        "/recuentos/hora",
        "desde=2026-11-02T06:00:00Z&hasta=2026-11-02T12:00:00Z",
    )
    assert estado == 200
    assert (datos["desde"], datos["hasta"], datos["total"]) == ("2026-11-02T06:00:00.000Z", "2026-11-02T12:00:00.000Z", 3)
    assert [v["recuento"] for v in datos["ventanas"]] == [0, 2, 0, 1, 0, 0]


def test_recuentos_por_hora_mas_de_31_dias_es_400():
    estado, datos = obtener(
        app_con(), "/recuentos/hora", "desde=2026-09-01T00:00:00Z&hasta=2026-11-01T00:00:00Z"
    )
    assert estado == 400 and datos["parametro"] == "hasta"


def test_distribucion_con_nulos_aparte():
    estado, datos = obtener(app_con(BdFalsa(lambda s, p: [(None, 2), (5, 3)])), "/distribuciones/magnitud")
    assert estado == 200
    assert (datos["unidad"], datos["total"], datos["sin_valor"]) == ("magnitud", 5, 2)
    assert datos["intervalos"][5] == {"desde": 4, "hasta": 5, "etiqueta": "4–5", "recuento": 3}
    estado, datos = obtener(app_con(BdFalsa(lambda s, p: [])), "/distribuciones/profundidad")
    assert datos["unidad"] == "km" and datos["total"] == 0 and len(datos["intervalos"]) == 9


# --- /comparacion-historica ------------------------------------------------


def comparacion_bd(existe=True, cargado=True, n24=10, n2025=18302):
    def responder(sql, params):
        if "to_regclass" in sql:
            return [(existe,)]
        if "EXISTS" in sql:
            return [(cargado,)]
        if "historico.evento_2025" in sql:
            return [(n2025,)]
        return [(n24,)]

    return BdFalsa(responder)


def test_comparacion_con_historico():
    bd = comparacion_bd()
    estado, datos = obtener(app_con(bd), "/comparacion-historica")
    assert estado == 200
    assert datos["historico_2025"]["estado"] == "cargado"
    assert datos["historico_2025"]["media_diaria"] == pytest.approx(50.14, abs=0.01)
    assert datos["cociente"] == pytest.approx(10 / (18302 / 365), abs=0.01)
    assert datos["ventana_actual"]["eventos"] == 10
    assert datos["filtros_efectivos"] == {"magnitud_min": 4.0, "magnitud_max": None, "pais": None, "subregion": None}
    assert datos["aviso"] and "incompleto" in datos["aviso"]
    # Las 24 h son de la base viva, con magnitud mínima 4; el histórico no usa fechas ni sintéticos.
    sql_vivo, params_vivo = bd.llamadas[0]
    assert "live.evento_actual" in sql_vivo and "NOT sintetico" in sql_vivo and 4.0 in params_vivo
    sql_hist, params_hist = bd.llamadas[-1]
    assert "historico.evento_2025" in sql_hist and "sintetico" not in sql_hist and "ocurrencia" not in sql_hist
    assert params_hist == [4.0]


def test_la_magnitud_minima_efectiva_es_el_maximo_de_4_y_la_pedida():
    estado, datos = obtener(app_con(comparacion_bd()), "/comparacion-historica", "magnitud_min=2")
    assert datos["filtros_efectivos"]["magnitud_min"] == 4.0
    estado, datos = obtener(app_con(comparacion_bd()), "/comparacion-historica", "magnitud_min=5.5&pais=USA")
    assert datos["filtros_efectivos"]["magnitud_min"] == 5.5 and datos["filtros_efectivos"]["pais"] == "USA"


def test_pais_sin_eventos_en_2025_media_cero_con_aviso():
    estado, datos = obtener(app_con(comparacion_bd(n24=3, n2025=0)), "/comparacion-historica", "pais=ATA")
    assert datos["historico_2025"]["estado"] == "cargado"
    assert datos["historico_2025"]["eventos"] == 0 and datos["historico_2025"]["media_diaria"] == 0
    assert datos["cociente"] is None and datos["aviso"]


@pytest.mark.parametrize("existe,cargado", [(False, False), (True, False)])
def test_historico_no_cargado_inexistente_o_vacio(existe, cargado):
    bd = comparacion_bd(existe=existe, cargado=cargado, n24=7)
    estado, datos = obtener(app_con(bd), "/comparacion-historica")
    assert estado == 200
    assert datos["historico_2025"] == {"estado": "no_cargado", "eventos": None, "dias": 365, "media_diaria": None}
    assert datos["cociente"] is None
    assert datos["ventana_actual"]["eventos"] == 7
    assert "no está cargado" in datos["aviso"]
    # Con la tabla ausente nunca se agrega sobre ella (cerraría la conexión compartida).
    assert not any("count(*) FROM historico.evento_2025" in sql for sql, _ in bd.llamadas)


# --- /status ---------------------------------------------------------------


def test_status_con_la_base_caida_es_200_con_nulos():
    estado, datos = obtener(app_con(BdFalsa(error=SinConexion("x"))), "/status")
    assert estado == 200
    assert datos["base_de_datos"] == "fallida"
    for campo in ("eventos_reales", "ultima_ingesta_correcta", "periodo_consultado", "datos_desactualizados"):
        assert datos[campo] is None
    assert datos["umbral_datos_desactualizados_segundos"] == 300


def test_el_umbral_configurado_llega_a_status():
    datos = obtener(app_con(BdFalsa(error=SinConexion("x")), DATOS_DESACTUALIZADOS_SEGUNDOS="600"), "/status")[1]
    assert datos["umbral_datos_desactualizados_segundos"] == 600
