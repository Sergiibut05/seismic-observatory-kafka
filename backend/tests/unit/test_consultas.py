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


@pytest.mark.parametrize("nombre", sorted(CONSTANTES))
def test_las_constantes_no_leen_replay(nombre):
    assert "replay." not in CONSTANTES[nombre]


def test_el_where_completo_tampoco_escribe():
    f = Filtros(pais="USA", subregion="x", magnitud_min=1.0, magnitud_max=2.0, incluir_sinteticos=True)
    donde, _ = construir_where(f)
    for nombre, plantilla in CONSTANTES.items():
        sentencia = consultas.con_where(plantilla, donde)
        assert re.match(r"^(SELECT|WITH)\b", sentencia) and not PROHIBIDAS.search(sentencia), nombre
        assert "{where}" not in sentencia


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
