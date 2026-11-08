"""La API es de solo lectura: todo el SQL de `api/` es SELECT y los valores del usuario van en `%s`."""

import re
from pathlib import Path

import pytest

from observatorio.api import consultas
from observatorio.api import estado as modulo_estado
from observatorio.api.filtros import Filtros, construir_where

CONSTANTES = {
    nombre: valor
    for modulo in (consultas, modulo_estado)
    for nombre, valor in vars(modulo).items()
    if nombre.startswith("SQL_") and isinstance(valor, str)
}
PROHIBIDAS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|COPY|MERGE|CALL|DO|VACUUM|SET)\b",
    re.IGNORECASE,
)


def test_hay_constantes_sql_que_comprobar():
    assert len(CONSTANTES) >= 15


@pytest.mark.parametrize("nombre", sorted(CONSTANTES))
def test_toda_constante_sql_es_select(nombre):
    sentencia = CONSTANTES[nombre]
    assert re.match(r"^(SELECT|WITH)\b", sentencia), nombre
    assert not PROHIBIDAS.search(sentencia), nombre
    assert ";" not in sentencia, nombre


# Las plantillas leen replay solo a través de `{tabla}` (diccionario cerrado); únicamente las
# consultas explícitas de existencia, recuento y ancla de replay nombran la tabla.
REPLAY_EXPLICITAS = {"SQL_REPLAY_EXISTE", "SQL_REPLAY_RECUENTO", "SQL_REPLAY_ULTIMA_OCURRENCIA"}


@pytest.mark.parametrize("nombre", sorted(CONSTANTES))
def test_las_constantes_solo_leen_replay_por_la_plantilla_o_de_forma_explicita(nombre):
    if nombre in REPLAY_EXPLICITAS:
        assert "replay.evento_actual" in CONSTANTES[nombre]
    else:
        assert "replay." not in CONSTANTES[nombre]


def test_las_consultas_de_replay_existen():
    assert REPLAY_EXPLICITAS <= set(CONSTANTES)
    assert "to_regclass" in consultas.SQL_REPLAY_EXISTE
    assert "count(*)" in consultas.SQL_REPLAY_RECUENTO
    assert "max(ocurrencia)" in consultas.SQL_REPLAY_ULTIMA_OCURRENCIA

def test_el_where_completo_tampoco_escribe():
    f = Filtros(pais="USA", subregion="x", magnitud_min=1.0, magnitud_max=2.0, incluir_sinteticos=True)
    donde, _ = construir_where(f)
    for modo in ("live", "replay"):
        for nombre, plantilla in CONSTANTES.items():
            sentencia = consultas.con_where(plantilla, donde, modo)
            assert re.match(r"^(SELECT|WITH)\b", sentencia) and not PROHIBIDAS.search(sentencia), nombre
            assert "{where}" not in sentencia and "{tabla}" not in sentencia


PLANTILLAS_CON_TABLA = [
    "SQL_TOTAL", "SQL_LISTA", "SQL_MAPA", "SQL_RECUENTO_PAIS", "SQL_RECUENTO_SUBREGION",
    "SQL_RECUENTO_HORA", "SQL_DISTRIBUCION_MAGNITUD", "SQL_DISTRIBUCION_PROFUNDIDAD",
]


@pytest.mark.parametrize("nombre", PLANTILLAS_CON_TABLA)
def test_la_plantilla_apunta_a_live_o_a_replay_segun_el_modo(nombre):
    plantilla = CONSTANTES[nombre]
    assert "{tabla}" in plantilla
    en_live = consultas.con_where(plantilla, " WHERE NOT sintetico", "live")
    en_replay = consultas.con_where(plantilla, " WHERE NOT sintetico", "replay")
    assert "live.evento_actual" in en_live and "replay." not in en_live
    assert "replay.evento_actual" in en_replay and "live.evento_actual" not in en_replay


def test_el_modo_por_defecto_es_live():
    assert "live.evento_actual" in consultas.con_where(consultas.SQL_TOTAL, "")


@pytest.mark.parametrize("modo", ["otro", "", "LIVE", "live; DROP TABLE x", None])
def test_un_modo_ajeno_a_las_tablas_lanza_key_error(modo):
    with pytest.raises(KeyError):
        consultas.con_where(consultas.SQL_TOTAL, "", modo)


def test_las_tablas_son_un_diccionario_cerrado():
    assert consultas.TABLAS == {"live": "live.evento_actual", "replay": "replay.evento_actual"}


def test_el_historico_no_usa_la_plantilla_de_tabla():
    sentencia = consultas.con_where(consultas.SQL_HISTORICO_RECUENTO, " WHERE magnitud >= %s", "live")
    assert "historico.evento_2025" in sentencia


def test_lista_y_mapa_traen_la_ingesta_como_ultima_columna():
    assert "e.ingested_at FROM" in consultas.SQL_LISTA
    assert "sintetico, ingested_at FROM" in consultas.SQL_MAPA


def test_los_marcadores_coinciden_con_los_parametros():
    f = Filtros(pais="USA", magnitud_min=1.0)
    donde, params = construir_where(f)
    assert consultas.con_where(consultas.SQL_TOTAL, donde).count("%s") == len(params)
    # La lista añade LIMIT y OFFSET.
    assert consultas.con_where(consultas.SQL_LISTA, donde).count("%s") == len(params) + 2
    assert consultas.con_where(consultas.SQL_MAPA, donde).count("%s") == len(params) + 1


def test_el_orden_de_lista_y_mapa_es_ocurrencia_desc_y_event_id():
    assert "ORDER BY ocurrencia DESC, event_id ASC" in consultas.SQL_LISTA
    assert "ORDER BY e.ocurrencia DESC, e.event_id ASC" in consultas.SQL_LISTA
    assert "ORDER BY ocurrencia DESC, event_id ASC" in consultas.SQL_MAPA


def test_la_comparacion_no_lee_la_tabla_de_2025_sin_comprobar_que_existe():
    assert "to_regclass" in consultas.SQL_HISTORICO_EXISTE
    assert "EXISTS" in consultas.SQL_HISTORICO_CARGADO


def test_ningun_modulo_de_la_api_escribe():
    # Ni siquiera fuera de las constantes: nada de execute de escritura ni DDL en `api/`.
    carpeta = Path(consultas.__file__).parent
    for fichero in carpeta.glob("*.py"):
        texto = fichero.read_text(encoding="utf-8")
        assert not re.search(r"\b(INSERT INTO|UPDATE \w+\.\w+ SET|DELETE FROM|CREATE (TABLE|INDEX|SCHEMA)|DROP )", texto), fichero.name
        assert "transaccion(" not in texto, fichero.name
