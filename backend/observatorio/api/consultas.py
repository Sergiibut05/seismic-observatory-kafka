"""SQL de la API (feature 005): solo `SELECT`, siempre con `%s` para los valores del usuario.

Las constantes se completan con el `WHERE` de `filtros.construir_where` (fragmentos constantes) y
con la tabla de `TABLAS` (feature 007: `modo=live|replay`). Del usuario solo llega la clave del
diccionario cerrado, nunca texto que se pegue en el SQL; `test_consultas.py` comprueba que ninguna
sentencia escribe en la base.
"""

from observatorio.api.calculos import BORDES_MAGNITUD, BORDES_PROFUNDIDAD

ESTADO_ACTUAL = "live.evento_actual"
ESTADO_REPLAY = "replay.evento_actual"
HISTORICO_2025 = "historico.evento_2025"

# Diccionario cerrado: `modo` (ya validado) → tabla de estado actual.
TABLAS = {"live": ESTADO_ACTUAL, "replay": ESTADO_REPLAY}

# Orden común de lista y mapa: `ocurrencia DESC, event_id ASC` (usa evento_actual_ocurrencia_idx en live).
_ORDEN = " ORDER BY ocurrencia DESC, event_id ASC"


def _bordes(bordes: tuple[int, ...]) -> str:
    # Constantes del código, nunca texto del usuario.
    return "ARRAY[" + ", ".join(str(b) for b in bordes) + "]::float8[]"


SQL_TOTAL = "SELECT count(*) FROM {tabla}{where}"

SQL_LISTA = (
    "SELECT e.event_id, e.ocurrencia, e.updated, e.magnitud, e.profundidad, e.longitud, e.latitud, "
    "e.pais_codigo, e.pais_nombre, p.subregion, e.sintetico, e.ingested_at "
    "FROM (SELECT * FROM {tabla}{where}" + _ORDEN + " LIMIT %s OFFSET %s) e "
    "LEFT JOIN ingesta.pais p ON p.codigo = e.pais_codigo "
    "ORDER BY e.ocurrencia DESC, e.event_id ASC"
)

SQL_MAPA = (
    "SELECT event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud, pais_nombre, "
    "sintetico, ingested_at "
    "FROM {tabla}{where}" + _ORDEN + " LIMIT %s"
)

SQL_RECUENTO_PAIS = (
    "SELECT pais_codigo, pais_nombre, count(*) FROM {tabla}{where}"
    " GROUP BY pais_codigo, pais_nombre ORDER BY count(*) DESC, pais_nombre ASC"
)

# `pais_codigo IS NULL` distingue «Sin país asignado» de un país sin subregión en el catálogo.
SQL_RECUENTO_SUBREGION = (
    "SELECT sp.subregion, (e.pais_codigo IS NULL), count(*) "
    "FROM (SELECT pais_codigo FROM {tabla}{where}) e "
    "LEFT JOIN ingesta.pais sp ON sp.codigo = e.pais_codigo "
    "GROUP BY sp.subregion, (e.pais_codigo IS NULL) ORDER BY count(*) DESC"
)

SQL_RECUENTO_HORA = (
    "SELECT date_trunc('hour', ocurrencia, 'UTC'), count(*) FROM {tabla}{where}"
    " GROUP BY 1 ORDER BY 1"
)

# `width_bucket` sobre los bordes: 0 = por debajo del primero, N = desde el último, NULL = sin valor.
SQL_DISTRIBUCION_MAGNITUD = (
    f"SELECT width_bucket(magnitud, {_bordes(BORDES_MAGNITUD)}), count(*) FROM " + "{tabla}{where}"
    " GROUP BY 1"
)
SQL_DISTRIBUCION_PROFUNDIDAD = (
    f"SELECT width_bucket(profundidad, {_bordes(BORDES_PROFUNDIDAD)}), count(*) FROM " + "{tabla}{where}"
    " GROUP BY 1"
)

# Comparación: la tabla de 2025 puede no existir; `to_regclass` evita consultarla (una tabla
# inexistente en `consultar` cerraría la conexión compartida).
SQL_HISTORICO_EXISTE = f"SELECT to_regclass('{HISTORICO_2025}') IS NOT NULL"
SQL_HISTORICO_CARGADO = f"SELECT EXISTS (SELECT 1 FROM {HISTORICO_2025})"
SQL_HISTORICO_RECUENTO = f"SELECT count(*) FROM {HISTORICO_2025}" + "{where}"

# Replay (feature 007): igual que el histórico, primero `to_regclass` y después el recuento.
SQL_REPLAY_EXISTE = f"SELECT to_regclass('{ESTADO_REPLAY}') IS NOT NULL"
SQL_REPLAY_RECUENTO = f"SELECT count(*) FROM {ESTADO_REPLAY}"
# Ancla de la ventana horaria en replay: el último `ocurrencia` (los eventos no son de hoy).
SQL_REPLAY_ULTIMA_OCURRENCIA = f"SELECT max(ocurrencia) FROM {ESTADO_REPLAY}"

# /status
SQL_ULTIMA_INGESTA = (
    "SELECT acabada_en FROM ingesta.consultas "
    "WHERE http_status = 200 AND error IS NULL ORDER BY id DESC LIMIT 1"
)
SQL_PERIODO = f"SELECT min(ocurrencia), max(ocurrencia) FROM {ESTADO_ACTUAL} WHERE NOT sintetico"


def con_where(sql: str, donde: str, modo: str = "live") -> str:
    """Inserta el `WHERE` (constante, con `%s`) y la tabla de `modo` en la plantilla.

    Las únicas interpolaciones del módulo. `modo` fuera de `TABLAS` lanza `KeyError`.
    """
    tabla = TABLAS[modo]
    return sql.replace("{tabla}", tabla).replace("{where}", donde)
