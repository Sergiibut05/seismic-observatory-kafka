"""SQL de la API (feature 005): solo `SELECT`, siempre con `%s` para los valores del usuario.

Las constantes se completan con el `WHERE` de `filtros.construir_where` (fragmentos constantes);
`test_consultas.py` comprueba que ninguna sentencia escribe en la base.
"""

from observatorio.api.calculos import BORDES_MAGNITUD, BORDES_PROFUNDIDAD

ESTADO_ACTUAL = "live.evento_actual"
HISTORICO_2025 = "historico.evento_2025"

# Orden común de lista y mapa: `ocurrencia DESC, event_id ASC` (usa evento_actual_ocurrencia_idx).
_ORDEN = " ORDER BY ocurrencia DESC, event_id ASC"


def _bordes(bordes: tuple[int, ...]) -> str:
    # Constantes del código, nunca texto del usuario.
    return "ARRAY[" + ", ".join(str(b) for b in bordes) + "]::float8[]"


SQL_TOTAL = f"SELECT count(*) FROM {ESTADO_ACTUAL}" + "{where}"

SQL_LISTA = (
    "SELECT e.event_id, e.ocurrencia, e.updated, e.magnitud, e.profundidad, e.longitud, e.latitud, "
    "e.pais_codigo, e.pais_nombre, p.subregion, e.sintetico "
    f"FROM (SELECT * FROM {ESTADO_ACTUAL}" + "{where}" + _ORDEN + " LIMIT %s OFFSET %s) e "
    "LEFT JOIN ingesta.pais p ON p.codigo = e.pais_codigo "
    "ORDER BY e.ocurrencia DESC, e.event_id ASC"
)

SQL_MAPA = (
    "SELECT event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud, pais_nombre, sintetico "
    f"FROM {ESTADO_ACTUAL}" + "{where}" + _ORDEN + " LIMIT %s"
)

SQL_RECUENTO_PAIS = (
    f"SELECT pais_codigo, pais_nombre, count(*) FROM {ESTADO_ACTUAL}" + "{where}"
    " GROUP BY pais_codigo, pais_nombre ORDER BY count(*) DESC, pais_nombre ASC"
)

# `pais_codigo IS NULL` distingue «Sin país asignado» de un país sin subregión en el catálogo.
SQL_RECUENTO_SUBREGION = (
    "SELECT sp.subregion, (e.pais_codigo IS NULL), count(*) "
    f"FROM (SELECT pais_codigo FROM {ESTADO_ACTUAL}" + "{where}) e "
    "LEFT JOIN ingesta.pais sp ON sp.codigo = e.pais_codigo "
    "GROUP BY sp.subregion, (e.pais_codigo IS NULL) ORDER BY count(*) DESC"
)

SQL_RECUENTO_HORA = (
    f"SELECT date_trunc('hour', ocurrencia, 'UTC'), count(*) FROM {ESTADO_ACTUAL}" + "{where}"
    " GROUP BY 1 ORDER BY 1"
)

# `width_bucket` sobre los bordes: 0 = por debajo del primero, N = desde el último, NULL = sin valor.
SQL_DISTRIBUCION_MAGNITUD = (
    f"SELECT width_bucket(magnitud, {_bordes(BORDES_MAGNITUD)}), count(*) FROM {ESTADO_ACTUAL}" + "{where}"
    " GROUP BY 1"
)
SQL_DISTRIBUCION_PROFUNDIDAD = (
    f"SELECT width_bucket(profundidad, {_bordes(BORDES_PROFUNDIDAD)}), count(*) FROM {ESTADO_ACTUAL}"
    + "{where}"
    " GROUP BY 1"
)

# Comparación: la tabla de 2025 puede no existir; `to_regclass` evita consultarla (una tabla
# inexistente en `consultar` cerraría la conexión compartida).
SQL_HISTORICO_EXISTE = f"SELECT to_regclass('{HISTORICO_2025}') IS NOT NULL"
SQL_HISTORICO_CARGADO = f"SELECT EXISTS (SELECT 1 FROM {HISTORICO_2025})"
SQL_HISTORICO_RECUENTO = f"SELECT count(*) FROM {HISTORICO_2025}" + "{where}"

# /status
SQL_ULTIMA_INGESTA = (
    "SELECT acabada_en FROM ingesta.consultas "
    "WHERE http_status = 200 AND error IS NULL ORDER BY id DESC LIMIT 1"
)
SQL_PERIODO = f"SELECT min(ocurrencia), max(ocurrencia) FROM {ESTADO_ACTUAL} WHERE NOT sintetico"


def con_where(sql: str, where: str) -> str:
    """Inserta el `WHERE` (constante, con `%s`) en la plantilla; la única interpolación del módulo."""
    return sql.replace("{where}", where)
