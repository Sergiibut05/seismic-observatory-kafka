"""Mediciones de tiempo y memoria del apartado 10 del enunciado (feature 007).

Tres operaciones con tres tamaños de entrada, sobre datos SINTÉTICOS (prefijo `synthetic-medicion-`):
búsqueda de la última versión por id, país de un punto y agregación por hora, en memoria y en
PostgreSQL (esquema temporal `medicion`, sin y con índice). Escribe un informe Markdown en stdout
y los logs en stderr. Garantía: solo escribe en el esquema `medicion` y lo borra al terminar; los
recuentos de `live`, `replay` e `historico` se comparan antes y después y, si no cumplen, sale con 1.

    docker compose exec -T producer python -m observatorio.mediciones --tamanos 1000,10000,100000 --repeticiones 5
"""

import argparse
import gc
import itertools
import logging
import math
import os
import platform
import random
import re
import shutil
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg
import shapely
from shapely.geometry import Point

from observatorio.common.catalogo import SIN_PAIS, IndicePaises, construir_indice
from observatorio.common.config import ajustes_productor, cargar_o_salir
from observatorio.common.db import parametros_conexion
from observatorio.common.logging import FormateadorClaveValor, registrar

_log = logging.getLogger("observatorio.mediciones")

SEMILLA = 20261108
TAMANOS_DEFECTO = "1000,10000,100000"
REPETICIONES_DEFECTO = 5
BUSQUEDAS = 200
HORA_MS = 3_600_000
OBJETIVO_EXTRAPOLACION = 100_000_000
PREFIJO = "synthetic-medicion-"

_BASE_MS = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
_DIAS_MS = 30 * 86_400_000
_ESQUEMA = "medicion"


# --- estadístico y medición ---------------------------------------------------


def estadistica(muestras: list[float]) -> tuple[float, float]:
    """Mediana y máximo de las repeticiones."""
    if not muestras:
        raise ValueError("no hay muestras")
    return statistics.median(muestras), max(muestras)


def parsear_tamanos(texto: str) -> tuple[int, ...]:
    try:
        valores = [int(trozo) for trozo in texto.split(",")]
    except ValueError:
        raise ValueError(f"tamaños no numéricos: {texto!r}") from None
    if not valores or any(valor < 1 for valor in valores):
        raise ValueError("los tamaños deben ser enteros positivos")
    if len(set(valores)) != len(valores):
        raise ValueError("hay tamaños repetidos")
    return tuple(sorted(valores))


@dataclass
class Resultado:
    muestras_ms: list[float]
    pico_kib: float
    valor: object


def medir(funcion: Callable[[], object], repeticiones: int, con_memoria: bool = True) -> Resultado:
    """Tiempo (`perf_counter`, una muestra por repetición) y pico de `tracemalloc` en una pasada aparte.

    `tracemalloc` ralentiza el código, así que la memoria nunca se mide en las pasadas de tiempo.
    """
    muestras: list[float] = []
    valor = None
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        valor = funcion()
        muestras.append((time.perf_counter() - inicio) * 1000)
    pico = 0.0
    if con_memoria:
        gc.collect()
        tracemalloc.start()
        try:
            funcion()
            pico = tracemalloc.get_traced_memory()[1] / 1024
        finally:
            tracemalloc.stop()
    return Resultado(muestras, pico, valor)


@dataclass(frozen=True)
class Medida:
    bloque: str
    operacion: str
    tamano: int
    repeticiones: int
    mediana_ms: float
    maximo_ms: float
    pico_kib: float
    nota: str = ""
    modelo: str = ""  # lineal | constante | n_log_n: cómo escala el tiempo con N
    memoria_lineal: bool = False  # el pico crece con N (se extrapola en bytes por elemento)


def _medida(bloque, operacion, tamano, resultado: Resultado, nota="", modelo="", memoria_lineal=False) -> Medida:
    mediana, maximo = estadistica(resultado.muestras_ms)
    return Medida(
        bloque, operacion, tamano, len(resultado.muestras_ms), mediana, maximo, resultado.pico_kib, nota, modelo, memoria_lineal
    )


# --- datos sintéticos reproducibles -------------------------------------------


def generar_versiones(n: int, semilla: int = SEMILLA) -> list[tuple[str, int]]:
    """`n` versiones `(id, updated_ms)` de `n // 2` eventos, mezcladas con semilla fija."""
    eventos = max(1, n // 2)
    versiones = [(f"{PREFIJO}{i % eventos}", _BASE_MS + i * 1000) for i in range(n)]
    random.Random(semilla).shuffle(versiones)
    return versiones


def ids_de_busqueda(versiones: list[tuple[str, int]], cantidad: int, semilla: int = SEMILLA) -> list[str]:
    ids = sorted({event_id for event_id, _ in versiones})
    return random.Random(semilla).choices(ids, k=cantidad)


def generar_puntos(n: int, semilla: int = SEMILLA) -> list[tuple[float, float]]:
    """`n` puntos `(longitud, latitud)` uniformes sobre el globo (no siguen la sismicidad real)."""
    aleatorio = random.Random(semilla)
    return [(aleatorio.uniform(-180, 180), aleatorio.uniform(-90, 90)) for _ in range(n)]


def generar_instantes(n: int, semilla: int = SEMILLA) -> list[int]:
    """`n` instantes en ms epoch repartidos en 30 días a partir del 2026-10-01 UTC."""
    aleatorio = random.Random(semilla)
    return [_BASE_MS + aleatorio.randrange(_DIAS_MS) for _ in range(n)]


# --- búsqueda de la última versión: lista frente a dict -----------------------


def ultima_version_lista(versiones: list[tuple[str, int]], event_id: str) -> int | None:
    """Recorrido secuencial, O(n): hay que mirar todas las versiones para saber cuál es la última."""
    mejor = None
    for identificador, updated in versiones:
        if identificador == event_id and (mejor is None or updated > mejor):
            mejor = updated
    return mejor


def construir_indice_versiones(versiones: list[tuple[str, int]]) -> dict[str, int]:
    """Diccionario id → `updated` más reciente. Construcción O(n), consulta O(1) medio."""
    indice: dict[str, int] = {}
    for event_id, updated in versiones:
        if updated > indice.get(event_id, -1):
            indice[event_id] = updated
    return indice


# --- país: recorrido secuencial frente a STRtree ------------------------------


def preparar_secuencial(indice: IndicePaises) -> list:
    """Copias preparadas (`shapely.prepare`) de los mismos polígonos del índice: la línea base más favorable."""
    figuras = [shapely.from_wkb(shapely.to_wkb(figura)) for figura in indice.arbol.geometries]
    shapely.prepare(figuras)
    return figuras


def asignar_secuencial(figuras: list, indice: IndicePaises, puntos: list[tuple[float, float]]) -> list[tuple[str | None, str]]:
    """Prueba cada punto contra todos los polígonos, O(m·v); desempata como `IndicePaises.asignar`."""
    areas = indice.areas
    resultado = []
    for longitud, latitud in puntos:
        punto = Point(longitud, latitud)
        elegido = -1
        for posicion, figura in enumerate(figuras):
            if figura.covers(punto) and (elegido < 0 or areas[posicion] < areas[elegido]):
                elegido = posicion
        if elegido < 0:
            resultado.append((None, SIN_PAIS))
        else:
            resultado.append((indice.codigos[elegido], indice.nombres[elegido]))
    return resultado


def asignar_con_arbol(indice: IndicePaises, puntos: list[tuple[float, float]]) -> list[tuple[str | None, str]]:
    return [indice.asignar(longitud, latitud) for longitud, latitud in puntos]


# --- agregación por hora UTC --------------------------------------------------


def agregar_con_dict(instantes: list[int]) -> dict[int, int]:
    """Un contador por hora (inicio de la hora en ms epoch UTC). O(n)."""
    conteo: dict[int, int] = {}
    for ms in instantes:
        hora = ms // HORA_MS * HORA_MS
        conteo[hora] = conteo.get(hora, 0) + 1
    return conteo


def agregar_ordenando(instantes: list[int]) -> dict[int, int]:
    """Ordenar y agrupar por hora. O(n log n)."""
    return {
        hora * HORA_MS: sum(1 for _ in grupo)
        for hora, grupo in itertools.groupby(sorted(instantes), key=lambda ms: ms // HORA_MS)
    }


# --- PostgreSQL: solo el esquema `medicion` -----------------------------------

_FUERA_DE_MEDICION = re.compile(r"\b(live|replay|historico|ingesta)\s*\.", re.IGNORECASE)
_DENTRO_DE_MEDICION = re.compile(r"\bmedicion\b")


def validar_escritura(sentencia: str) -> None:
    """Guarda en ejecución: una sola sentencia que nombra `medicion` y ningún otro esquema del proyecto."""
    if ";" in sentencia:
        raise ValueError("una escritura debe ser una sola sentencia")
    if not _DENTRO_DE_MEDICION.search(sentencia):
        raise ValueError(f"la escritura no menciona el esquema medicion: {sentencia[:60]!r}")
    if _FUERA_DE_MEDICION.search(sentencia):
        raise ValueError(f"la escritura toca un esquema que no es medicion: {sentencia[:60]!r}")


def _plantillas(n: int) -> dict[str, str]:
    n = int(n)
    base = f"TIMESTAMPTZ '2026-10-01 00:00:00+00' + ((i::bigint * 7919) % 2592000) * interval '1 second'"
    return {
        "borrar": f"DROP SCHEMA IF EXISTS {_ESQUEMA} CASCADE",
        "esquema": f"CREATE SCHEMA {_ESQUEMA}",
        # Forma de live.evento_actual sin claves foráneas ni CHECK; la clave primaria se añade después.
        "tabla": (
            f"CREATE TABLE {_ESQUEMA}.evento ("
            "event_id text NOT NULL, updated timestamptz NOT NULL, ocurrencia timestamptz NOT NULL, "
            "magnitud double precision, profundidad double precision, "
            "longitud double precision NOT NULL, latitud double precision NOT NULL, "
            "pais_codigo text, pais_nombre text NOT NULL, source text NOT NULL, "
            "mode text NOT NULL DEFAULT 'live', sintetico boolean NOT NULL, "
            "ingested_at timestamptz NOT NULL, processed_at timestamptz NOT NULL DEFAULT clock_timestamp())"
        ),
        "carga": (
            f"INSERT INTO {_ESQUEMA}.evento (event_id, updated, ocurrencia, magnitud, profundidad, longitud, latitud, "
            "pais_codigo, pais_nombre, source, mode, sintetico, ingested_at) "
            f"SELECT '{PREFIJO}' || i, {base} + interval '60 seconds', {base}, "
            "(1.0 + ((i * 31) % 70) / 10.0)::double precision, ((i * 17) % 700)::double precision, "
            "(((i * 37) % 3600) / 10.0 - 180.0)::double precision, (((i * 53) % 1800) / 10.0 - 90.0)::double precision, "
            f"NULL, '{SIN_PAIS}', 'synthetic-medicion', 'live', true, {base} + interval '30 seconds' "
            f"FROM generate_series(1, {n}) AS i"
        ),
        "analizar": f"ANALYZE {_ESQUEMA}.evento",
        "clave": f"ALTER TABLE {_ESQUEMA}.evento ADD CONSTRAINT evento_pk PRIMARY KEY (event_id)",
        "indice": f"CREATE INDEX evento_ocurrencia_idx ON {_ESQUEMA}.evento (ocurrencia DESC, event_id)",
    }


def sentencias_de_escritura(n: int) -> tuple[str, ...]:
    return tuple(_plantillas(n).values())


def _consultas(n: int) -> dict[str, str]:
    return {
        "busqueda": f"SELECT * FROM {_ESQUEMA}.evento WHERE event_id = '{PREFIJO}{max(1, int(n) // 2)}'",
        "lista": (
            f"SELECT event_id, ocurrencia, magnitud FROM {_ESQUEMA}.evento "
            "ORDER BY ocurrencia DESC, event_id LIMIT 100"
        ),
        "ventana": (
            "SELECT date_trunc('hour', ocurrencia, 'UTC') AS hora, count(*) "
            f"FROM {_ESQUEMA}.evento "
            "WHERE ocurrencia >= TIMESTAMPTZ '2026-10-15 00:00:00+00' "
            "AND ocurrencia < TIMESTAMPTZ '2026-10-16 00:00:00+00' GROUP BY 1 ORDER BY 1"
        ),
    }


_TIEMPO = re.compile(r"Execution Time:\s*([0-9]+(?:\.[0-9]+)?)\s*ms")
_BUFFERS = re.compile(r"^\s*Buffers:\s*(.+?)\s*$")


def tiempo_de_ejecucion_ms(lineas: list[str]) -> float:
    for linea in lineas:
        encontrada = _TIEMPO.search(linea)
        if encontrada:
            return float(encontrada.group(1))
    raise ValueError("el plan no trae «Execution Time»")


def buffers_del_plan(lineas: list[str]) -> str:
    for linea in lineas:
        encontrada = _BUFFERS.match(linea)
        if encontrada:
            return encontrada.group(1)
    return "sin datos"


@dataclass(frozen=True)
class PruebaPostgres:
    tamano: int
    consulta: str
    con_indice: bool
    mediana_ms: float
    maximo_ms: float
    buffers: str
    plan: list[str]


@dataclass(frozen=True)
class TamanoRelacion:
    tamano: int
    total_sin_indice: int
    tabla: int
    indices: int
    total_con_indice: int
    clave_primaria: int
    indice_ocurrencia: int


def _escribir(conexion, sentencia: str) -> None:
    validar_escritura(sentencia)
    conexion.execute(sentencia)


def _tamano(conexion, objeto: str) -> int:
    return int(conexion.execute(f"SELECT pg_total_relation_size('{objeto}')").fetchone()[0])


def _explicar(conexion, tamano: int, con_indice: bool, repeticiones: int) -> list[PruebaPostgres]:
    pruebas = []
    for nombre, consulta in _consultas(tamano).items():
        tiempos: list[float] = []
        plan: list[str] = []
        for _ in range(repeticiones):
            plan = [fila[0] for fila in conexion.execute("EXPLAIN (ANALYZE, BUFFERS) " + consulta).fetchall()]
            tiempos.append(tiempo_de_ejecucion_ms(plan))
        mediana, maximo = estadistica(tiempos)
        pruebas.append(PruebaPostgres(tamano, nombre, con_indice, mediana, maximo, buffers_del_plan(plan), plan))
    return pruebas


def medir_postgres(conexion, tamanos: tuple[int, ...], repeticiones: int) -> tuple[list[PruebaPostgres], list[TamanoRelacion]]:
    """Por tamaño: tabla sintética sin índices, EXPLAIN, clave primaria e índice, EXPLAIN. Borra el esquema al final."""
    pruebas: list[PruebaPostgres] = []
    relaciones: list[TamanoRelacion] = []
    conexion.execute("SET statement_timeout = '300s'")
    try:
        for n in tamanos:
            plantillas = _plantillas(n)
            for paso in ("borrar", "esquema", "tabla", "carga", "analizar"):
                _escribir(conexion, plantillas[paso])
            registrar(_log, "info", bloque="postgres", tamano=n, fase="sin_indice")
            total_sin_indice = _tamano(conexion, f"{_ESQUEMA}.evento")
            pruebas += _explicar(conexion, n, False, repeticiones)
            for paso in ("clave", "indice", "analizar"):
                _escribir(conexion, plantillas[paso])
            registrar(_log, "info", bloque="postgres", tamano=n, fase="con_indice")
            pruebas += _explicar(conexion, n, True, repeticiones)
            tabla = int(conexion.execute(f"SELECT pg_relation_size('{_ESQUEMA}.evento')").fetchone()[0])
            clave = _tamano(conexion, f"{_ESQUEMA}.evento_pk")
            indice = _tamano(conexion, f"{_ESQUEMA}.evento_ocurrencia_idx")
            relaciones.append(
                TamanoRelacion(n, total_sin_indice, tabla, clave + indice, _tamano(conexion, f"{_ESQUEMA}.evento"), clave, indice)
            )
    finally:
        _escribir(conexion, _plantillas(1)["borrar"])
    return pruebas, relaciones


# --- garantía: recuentos antes y después --------------------------------------

_SINTETICO_MEDICION = f"event_id LIKE '{PREFIJO}%'"

# nombre → (SQL, política). Las tablas `live` sí cambian durante la medición: el productor sigue
# consultando USGS cada 60 s y el consumidor persiste. Por eso se cuentan solo las reales y se
# tolera que crezcan (nunca que decrezcan). Replay e histórico no los toca nadie: tienen que ser iguales.
RECUENTOS: dict[str, tuple[str, str]] = {
    "live.evento_actual (reales)": ("SELECT count(*) FROM live.evento_actual WHERE NOT sintetico", "no_decrece"),
    "live.versiones_evento (reales)": ("SELECT count(*) FROM live.versiones_evento WHERE NOT sintetico", "no_decrece"),
    "live.* con prefijo synthetic-medicion-": (
        f"SELECT (SELECT count(*) FROM live.evento_actual WHERE {_SINTETICO_MEDICION}) "
        f"+ (SELECT count(*) FROM live.versiones_evento WHERE {_SINTETICO_MEDICION})",
        "cero",
    ),
    "replay.evento_actual (reales)": ("SELECT count(*) FROM replay.evento_actual WHERE NOT sintetico", "igual"),
    "replay.versiones_evento (reales)": ("SELECT count(*) FROM replay.versiones_evento WHERE NOT sintetico", "igual"),
    "historico.evento_2025": ("SELECT count(*) FROM historico.evento_2025", "igual"),
}


def comparar_recuentos(antes: dict[str, int], despues: dict[str, int], estricto: bool = False) -> list[str]:
    """Lista de incumplimientos (vacía = garantía cumplida). `estricto` exige igualdad también en `live`."""
    fallos = []
    for nombre, valor_antes in antes.items():
        politica = RECUENTOS.get(nombre, (None, "igual"))[1]
        valor_despues = despues.get(nombre)
        if valor_despues is None:
            fallos.append(f"{nombre}: antes={valor_antes} después=sin dato")
            continue
        if politica == "no_decrece" and not estricto:
            correcto = valor_despues >= valor_antes
        elif politica == "cero":
            correcto = valor_despues == 0
        else:
            correcto = valor_despues == valor_antes
        if not correcto:
            fallos.append(f"{nombre}: antes={valor_antes} después={valor_despues}")
    return fallos


@dataclass
class Garantia:
    antes: dict[str, int]
    despues: dict[str, int]
    fallos: list[str]
    resultado: object = None
    error: str = ""

    @property
    def cumplida(self) -> bool:
        return not self.fallos and not self.error

    @property
    def codigo_salida(self) -> int:
        return 0 if self.cumplida else 1


def ejecutar_con_garantia(
    leer_recuentos: Callable[[], dict[str, int]], trabajo: Callable[[], object], estricto: bool = False
) -> Garantia:
    """Recuentos antes, trabajo, recuentos después (también si el trabajo falla) y veredicto."""
    antes = leer_recuentos()
    resultado = None
    error = ""
    try:
        resultado = trabajo()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    despues = leer_recuentos()
    return Garantia(antes, despues, comparar_recuentos(antes, despues, estricto), resultado, error)


# --- extrapolación (no medida) ------------------------------------------------


def extrapolar_constante(valor: float) -> float:
    return valor


def extrapolar_lineal(valor: float, tamano: int, objetivo: int) -> float:
    return valor * objetivo / tamano


def extrapolar_logaritmico(valor: float, tamano: int, objetivo: int) -> float:
    return valor * math.log(objetivo) / math.log(tamano)


def extrapolar_n_log_n(valor: float, tamano: int, objetivo: int) -> float:
    return valor * (objetivo * math.log(objetivo)) / (tamano * math.log(tamano))


def extrapolar_bytes(kib: float, tamano: int, objetivo: int) -> float:
    """Bytes de `objetivo` elementos a partir de los KiB medidos con `tamano`."""
    return kib * 1024 / tamano * objetivo


@dataclass(frozen=True)
class Extrapolacion:
    operacion: str
    modelo: str
    resultado: str


def fmt(valor: float, decimales: int = 2) -> str:
    """Formato español: punto de millares y coma decimal."""
    return f"{valor:,.{decimales}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def _duracion(ms: float) -> str:
    if ms < 1000:
        return f"{fmt(ms, 2)} ms"
    segundos = ms / 1000
    if segundos < 120:
        return f"{fmt(segundos, 1)} s"
    if segundos < 7200:
        return f"{fmt(segundos / 60, 1)} min"
    return f"{fmt(segundos / 3600, 1)} h"


def _memoria(bytes_: float) -> str:
    for unidad, factor in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if bytes_ >= factor:
            return f"{fmt(bytes_ / factor, 2)} {unidad}"
    return f"{fmt(bytes_, 0)} B"


_MODELO_PG = {
    ("busqueda", False): "lineal",
    ("busqueda", True): "log",
    ("lista", False): "lineal",
    ("lista", True): "constante",
    ("ventana", False): "lineal",
    ("ventana", True): "lineal",
}
_NOMBRE_MODELO = {
    "lineal": "O(n)",
    "constante": "O(1)",
    "log": "O(log n)",
    "n_log_n": "O(n log n)",
}


def _estimar(valor: float, modelo: str, tamano: int, objetivo: int) -> float:
    if modelo == "constante":
        return extrapolar_constante(valor)
    if modelo == "log":
        return extrapolar_logaritmico(valor, tamano, objetivo)
    if modelo == "n_log_n":
        return extrapolar_n_log_n(valor, tamano, objetivo)
    return extrapolar_lineal(valor, tamano, objetivo)


def calcular_extrapolaciones(
    medidas: list[Medida],
    pruebas: list[PruebaPostgres] | None,
    relaciones: list[TamanoRelacion] | None,
    objetivo: int = OBJETIVO_EXTRAPOLACION,
) -> list[Extrapolacion]:
    """Parte siempre de la medida del mayor tamaño. Es una estimación, nunca una medición."""
    resultado: list[Extrapolacion] = []
    if medidas:
        mayor = max(medida.tamano for medida in medidas)
        for medida in (m for m in medidas if m.tamano == mayor and m.modelo):
            tiempo = _duracion(_estimar(medida.mediana_ms, medida.modelo, medida.tamano, objetivo))
            texto = f"tiempo ≈ {tiempo}"
            if medida.memoria_lineal:
                texto += f"; memoria ≈ {_memoria(extrapolar_bytes(medida.pico_kib, medida.tamano, objetivo))}"
            resultado.append(Extrapolacion(f"{medida.bloque}: {medida.operacion}", _NOMBRE_MODELO[medida.modelo], texto))
    if pruebas:
        mayor_pg = max(prueba.tamano for prueba in pruebas)
        for prueba in (p for p in pruebas if p.tamano == mayor_pg):
            modelo = _MODELO_PG[(prueba.consulta, prueba.con_indice)]
            tiempo = _duracion(_estimar(prueba.mediana_ms, modelo, prueba.tamano, objetivo))
            indice = "con índice" if prueba.con_indice else "sin índice"
            resultado.append(Extrapolacion(f"postgres: {_ETIQUETA_CONSULTA.get(prueba.consulta, prueba.consulta)}, {indice}", _NOMBRE_MODELO[modelo], f"tiempo ≈ {tiempo}"))
    if relaciones:
        ultima = max(relaciones, key=lambda relacion: relacion.tamano)
        sin = ultima.total_sin_indice / ultima.tamano * objetivo
        con = ultima.total_con_indice / ultima.tamano * objetivo
        resultado.append(Extrapolacion("postgres: tamaño de la tabla", "O(n)", f"sin índices ≈ {_memoria(sin)}; con índices ≈ {_memoria(con)}"))
    return resultado


# --- equipo -------------------------------------------------------------------


def _rss_kib() -> int | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as fichero:
            for linea in fichero:
                if linea.startswith("VmRSS:"):
                    return int(linea.split()[1])
    except (OSError, ValueError):
        return None
    return None


def _cpu() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fichero:
            for linea in fichero:
                if linea.lower().startswith("model name"):
                    return linea.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "no disponible"


def _ram() -> str:
    try:
        with open("/proc/meminfo", encoding="utf-8") as fichero:
            for linea in fichero:
                if linea.startswith("MemTotal:"):
                    return f"{fmt(int(linea.split()[1]) / 1024 / 1024, 2)} GiB"
    except (OSError, ValueError):
        pass
    return "no disponible"


def describir_equipo(conexion=None) -> dict[str, str]:
    """Lo que ve el contenedor (la máquina virtual de Docker); el anfitrión Windows lo anota la memoria."""
    equipo = {
        "Sistema (contenedor)": platform.platform(),
        "CPU (modelo visible desde el contenedor)": _cpu(),
        "Núcleos visibles (`os.cpu_count`)": str(os.cpu_count()),
        "RAM visible (`/proc/meminfo`)": _ram(),
        "Python": platform.python_version(),
        "psycopg": psycopg.__version__,
        "shapely": shapely.__version__,
        "GEOS": shapely.geos_version_string,
    }
    uso = shutil.disk_usage("/")
    equipo["Disco del sistema de ficheros del contenedor"] = f"{fmt(uso.total / 1024**3, 1)} GiB, libres {fmt(uso.free / 1024**3, 1)} GiB"
    if conexion is not None:
        equipo["PostgreSQL"] = conexion.execute("SELECT version()").fetchone()[0].split(" on ")[0]
        for parametro in ("shared_buffers", "work_mem", "max_parallel_workers_per_gather"):
            equipo[f"PostgreSQL `{parametro}`"] = conexion.execute(f"SHOW {parametro}").fetchone()[0]
    return equipo


# --- bloque de memoria (Python) -----------------------------------------------


def medir_python(tamanos: tuple[int, ...], repeticiones: int, indice: IndicePaises) -> tuple[list[Medida], bool]:
    """Devuelve las medidas y si todas las comparaciones dieron el mismo resultado."""
    medidas: list[Medida] = []
    coinciden = True
    figuras = preparar_secuencial(indice)
    for n in tamanos:
        registrar(_log, "info", bloque="python", tamano=n)
        versiones = generar_versiones(n)
        ids = ids_de_busqueda(versiones, BUSQUEDAS)
        por_lista = medir(lambda: [ultima_version_lista(versiones, i) for i in ids], repeticiones)
        medidas.append(_medida("version", f"lista de tuplas: {BUSQUEDAS} búsquedas", n, por_lista, modelo="lineal"))
        medidas.append(
            _medida(
                "version",
                "lista de tuplas: construir (incluye mezclar)",
                n,
                medir(lambda: generar_versiones(n), repeticiones),
                modelo="lineal",
                memoria_lineal=True,
            )
        )
        medidas.append(
            _medida(
                "version",
                "diccionario: construir",
                n,
                medir(lambda: construir_indice_versiones(versiones), repeticiones),
                nota="el pico es el diccionario; las cadenas se comparten con la lista",
                modelo="lineal",
                memoria_lineal=True,
            )
        )
        diccionario = construir_indice_versiones(versiones)
        por_dict = medir(lambda: [diccionario[i] for i in ids], repeticiones)
        medidas.append(_medida("version", f"diccionario: {BUSQUEDAS} búsquedas", n, por_dict, modelo="constante"))
        coinciden &= por_lista.valor == por_dict.valor

        puntos = generar_puntos(n)
        secuencial = medir(lambda: asignar_secuencial(figuras, indice, puntos), repeticiones)
        medidas.append(
            _medida("pais", f"secuencial ({len(figuras)} polígonos preparados)", n, secuencial, modelo="lineal", memoria_lineal=True)
        )
        con_arbol = medir(lambda: asignar_con_arbol(indice, puntos), repeticiones)
        medidas.append(_medida("pais", "STRtree (`IndicePaises.asignar`)", n, con_arbol, modelo="lineal", memoria_lineal=True))
        coinciden &= secuencial.valor == con_arbol.valor

        instantes = generar_instantes(n)
        por_hora_dict = medir(lambda: agregar_con_dict(instantes), repeticiones)
        medidas.append(
            _medida("hora", "dict de contadores", n, por_hora_dict, nota="memoria casi constante: una entrada por hora (≤ 720)", modelo="lineal")
        )
        por_hora_orden = medir(lambda: agregar_ordenando(instantes), repeticiones)
        medidas.append(_medida("hora", "ordenar y agrupar", n, por_hora_orden, modelo="n_log_n", memoria_lineal=True))
        coinciden &= por_hora_dict.valor == por_hora_orden.valor
    return medidas, coinciden


# --- informe ------------------------------------------------------------------


@dataclass
class Informe:
    fecha: datetime
    comando: str
    equipo: dict[str, str]
    tamanos: tuple[int, ...]
    repeticiones: int
    medidas: list[Medida]
    coinciden_pais: bool
    postgres: list[PruebaPostgres] | None
    relaciones: list[TamanoRelacion] | None
    recuentos_antes: dict[str, int]
    recuentos_despues: dict[str, int]
    fallos: list[str]
    esquema_residual: int | None
    extrapolaciones: list[Extrapolacion] = field(default_factory=list)


_ETIQUETA_CONSULTA = {
    "busqueda": "búsqueda por event_id",
    "lista": "lista paginada (ORDER BY ocurrencia DESC LIMIT 100)",
    "ventana": "ventana horaria de 24 h (GROUP BY hora)",
}

_TITULOS = {
    "version": "1. Búsqueda de la última versión por id",
    "pais": "2. País de un punto",
    "hora": "3. Agregación por hora UTC",
}


def _tabla(cabecera: list[str], filas: list[list[str]]) -> list[str]:
    lineas = ["| " + " | ".join(cabecera) + " |", "| " + " | ".join("---" for _ in cabecera) + " |"]
    lineas += ["| " + " | ".join(fila) + " |" for fila in filas]
    return lineas


def renderizar(informe: Informe) -> str:
    fecha = informe.fecha.strftime("%Y-%m-%dT%H:%M:%SZ")
    tamanos = ", ".join(fmt(n, 0) for n in informe.tamanos)
    salida = [
        "# Mediciones de complejidad y memoria (feature 007)",
        "",
        f"- **Fecha de medición (UTC)**: {fecha}",
        f"- **Comando**: `{informe.comando}`",
        f"- **Tamaños de entrada**: {tamanos}; repeticiones por medida: {informe.repeticiones} (mediana y máximo).",
        "- **Datos**: SINTÉTICOS. Los generadores usan semilla fija; los ids llevan el prefijo "
        f"`{PREFIJO}` y `sintetico = true` en PostgreSQL. Nada de esto entra en el análisis real.",
        "",
        "## Equipo",
        "",
        *_tabla(["Concepto", "Valor"], [[clave, valor] for clave, valor in informe.equipo.items()]),
        "",
        "## Procedimiento",
        "",
        "- Tiempo: `time.perf_counter` por repetición; se informan la **mediana** y el **máximo** en milisegundos.",
        "- Memoria de Python: pico de `tracemalloc` (KiB) en una pasada aparte, porque `tracemalloc` ralentiza. "
        "Solo ve la memoria de Python: la de GEOS (el `STRtree`) queda fuera.",
        f"- Búsquedas: {BUSQUEDAS} ids elegidos al azar con semilla fija por cada medida.",
        "- País: puntos uniformes sobre el globo (no siguen la sismicidad real: la mayoría cae en el mar y sale sin país). "
        "El recorrido secuencial prueba cada punto contra los polígonos del catálogo, ya preparados con `shapely.prepare`.",
        "- PostgreSQL: esquema temporal `medicion` con una tabla de la forma de `live.evento_actual`; "
        "`EXPLAIN (ANALYZE, BUFFERS)` sin índices, después clave primaria e índice `(ocurrencia DESC, event_id)` y `ANALYZE`, "
        "y de nuevo `EXPLAIN`. El esquema se borra en un `finally`.",
        "- Se mide mientras la pila sigue encendida: el productor, el consumidor y PostgreSQL comparten la máquina, "
        "así que los tiempos incluyen ese ruido.",
        "",
    ]
    for bloque, titulo in _TITULOS.items():
        filas = [
            [
                fmt(m.tamano, 0),
                m.operacion,
                str(m.repeticiones),
                fmt(m.mediana_ms, 3),
                fmt(m.maximo_ms, 3),
                fmt(m.pico_kib, 1),
                m.nota,
            ]
            for m in informe.medidas
            if m.bloque == bloque
        ]
        salida += [
            f"## {titulo} (datos SINTÉTICOS, medido el {fecha})",
            "",
            *_tabla(["N", "Operación", "Repeticiones", "Mediana (ms)", "Máximo (ms)", "Pico memoria (KiB)", "Nota"], filas),
            "",
        ]
        if bloque == "pais":
            veredicto = "sí" if informe.coinciden_pais else "NO"
            salida += [f"Secuencial y `STRtree` asignan el mismo país a todos los puntos medidos: **{veredicto}**.", ""]
    salida += ["## 4. PostgreSQL sin y con índice (datos SINTÉTICOS `synthetic-medicion-`, " f"medido el {fecha})", ""]
    if informe.postgres is None or informe.relaciones is None:
        salida += ["En esta ejecución no se midió PostgreSQL (`--sin-base`).", ""]
    else:
        filas = [
            [
                fmt(p.tamano, 0),
                _ETIQUETA_CONSULTA.get(p.consulta, p.consulta),
                "con índice" if p.con_indice else "sin índice",
                fmt(p.mediana_ms, 3),
                fmt(p.maximo_ms, 3),
                p.buffers,
            ]
            for p in informe.postgres
        ]
        salida += [
            *_tabla(["N", "Consulta", "Índice", "Mediana (ms)", "Máximo (ms)", "Buffers (último plan)"], filas),
            "",
            "### Tamaño de las relaciones (`pg_total_relation_size`)",
            "",
            *_tabla(
                ["N", "Sin índices (bytes)", "Tabla (bytes)", "Índices (bytes)", "Total con índices (bytes)", "PK (bytes)", "Índice ocurrencia (bytes)"],
                [
                    [fmt(r.tamano, 0)] + [fmt(v, 0) for v in (r.total_sin_indice, r.tabla, r.indices, r.total_con_indice, r.clave_primaria, r.indice_ocurrencia)]
                    for r in informe.relaciones
                ],
            ),
            "",
            "### Planes (`EXPLAIN (ANALYZE, BUFFERS)`, último plan de cada serie)",
            "",
        ]
        for p in informe.postgres:
            indice = "con índice" if p.con_indice else "sin índice"
            etiqueta = _ETIQUETA_CONSULTA.get(p.consulta, p.consulta)
            salida += [f"#### N = {fmt(p.tamano, 0)} · {etiqueta} · {indice}", "", "```text", *p.plan, "```", ""]
    salida += [
        f"## 5. Extrapolación a {fmt(OBJETIVO_EXTRAPOLACION, 0)} de registros (EXTRAPOLACIÓN, no medida)",
        "",
        "Cada estimación parte de la mediana del mayor tamaño medido y de la complejidad teórica de la operación: "
        "lineal, logarítmica o constante. No tiene en cuenta que con esa escala los datos dejan de caber en RAM ni la caché; "
        "es un orden de magnitud, no un resultado.",
        "",
    ]
    if informe.extrapolaciones:
        salida += _tabla(
            ["Operación", "Modelo", "Estimación (NO medida)"],
            [[e.operacion, e.modelo, e.resultado] for e in informe.extrapolaciones],
        )
        salida.append("")
    else:
        salida += ["Sin estimaciones en esta ejecución.", ""]
    salida += ["## 6. Garantía: recuentos antes y después", ""]
    if informe.recuentos_antes:
        salida += [
            "Solo se cuentan filas reales. `live` puede crecer durante la medición porque la ingesta sigue en marcha "
            "(se tolera crecer, nunca decrecer); `replay` e `historico` tienen que quedar iguales.",
            "",
            *_tabla(
                ["Recuento", "Antes", "Después"],
                [
                    [nombre, fmt(antes, 0), fmt(informe.recuentos_despues.get(nombre, 0), 0)]
                    for nombre, antes in informe.recuentos_antes.items()
                ],
            ),
            "",
        ]
    if informe.esquema_residual is not None:
        salida += [f"Esquemas `medicion` tras la medición: {informe.esquema_residual} (esperado: 0).", ""]
    if informe.fallos:
        salida += ["**GARANTÍA NO CUMPLIDA**", "", *[f"- {fallo}" for fallo in informe.fallos], ""]
    else:
        salida += ["Garantía cumplida: nada fuera del esquema `medicion` cambió de forma inadmisible.", ""]
    return "\n".join(salida)


# --- entrada ------------------------------------------------------------------


def _configurar_logs(secretos: tuple[str, ...]) -> None:
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(FormateadorClaveValor("mediciones", secretos))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(logging.INFO)


def _leer_recuentos(conexion) -> dict[str, int]:
    return {nombre: int(conexion.execute(consulta).fetchone()[0]) for nombre, (consulta, _) in RECUENTOS.items()}


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(prog="observatorio.mediciones", description=__doc__.splitlines()[0])
    analizador.add_argument("--tamanos", default=TAMANOS_DEFECTO, help="tamaños separados por comas")
    analizador.add_argument("--repeticiones", type=int, default=REPETICIONES_DEFECTO)
    analizador.add_argument("--sin-base", action="store_true", help="solo las medidas en memoria")
    analizador.add_argument("--estricto", action="store_true", help="exige igualdad de recuentos también en live")
    argumentos = analizador.parse_args(argv)
    try:
        tamanos = parsear_tamanos(argumentos.tamanos)
    except ValueError as exc:
        analizador.error(str(exc))
    if argumentos.repeticiones < 1:
        analizador.error("--repeticiones debe ser >= 1")

    ajustes = None if argumentos.sin_base else cargar_o_salir("mediciones", ajustes_productor)
    _configurar_logs(ajustes.secretos() if ajustes else ())
    ruta_catalogo = os.environ.get("CATALOGO_PATH", "/catalogo/paises.geojson")
    registrar(_log, "iniciado", tamanos=",".join(map(str, tamanos)), repeticiones=argumentos.repeticiones, base=ajustes is not None)

    conexion = psycopg.connect(**parametros_conexion(ajustes.postgres)) if ajustes else None
    try:
        rss_antes = _rss_kib()
        inicio = time.perf_counter()
        indice = construir_indice(ruta_catalogo)
        construccion_ms = (time.perf_counter() - inicio) * 1000
        rss_despues = _rss_kib()
        equipo = describir_equipo(conexion)
        extra = f"{len(indice.codigos)} polígonos; construir el `STRtree` y las áreas: {fmt(construccion_ms, 1)} ms"
        if rss_antes is not None and rss_despues is not None:
            extra += f"; RSS del proceso +{fmt(rss_despues - rss_antes, 0)} KiB (aproximado, incluye GEOS)"
        equipo["Catálogo de países"] = extra

        def trabajo():
            medidas, coinciden = medir_python(tamanos, argumentos.repeticiones, indice)
            pruebas = relaciones = None
            if conexion is not None:
                pruebas, relaciones = medir_postgres(conexion, tamanos, argumentos.repeticiones)
            return medidas, coinciden, pruebas, relaciones

        garantia = ejecutar_con_garantia(
            (lambda: _leer_recuentos(conexion)) if conexion is not None else dict, trabajo, argumentos.estricto
        )
        residual = None
        if conexion is not None:
            residual = int(
                conexion.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'medicion'").fetchone()[0]
            )
    finally:
        if conexion is not None:
            conexion.close()

    if garantia.resultado is None:
        registrar(_log, "error", nivel="ERROR", motivo="medicion_fallida", detalle=garantia.error)
        return 1
    medidas, coinciden, pruebas, relaciones = garantia.resultado
    informe = Informe(
        fecha=datetime.now(timezone.utc),
        comando="python -m observatorio.mediciones " + " ".join(argv if argv is not None else sys.argv[1:]),
        equipo=equipo,
        tamanos=tamanos,
        repeticiones=argumentos.repeticiones,
        medidas=medidas,
        coinciden_pais=coinciden,
        postgres=pruebas,
        relaciones=relaciones,
        recuentos_antes=garantia.antes,
        recuentos_despues=garantia.despues,
        fallos=garantia.fallos + ([garantia.error] if garantia.error else []),
        esquema_residual=residual,
        extrapolaciones=calcular_extrapolaciones(medidas, pruebas, relaciones),
    )
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(renderizar(informe) + "\n")
    sys.stdout.flush()
    registrar(
        _log,
        "listo" if garantia.cumplida else "error",
        nivel="INFO" if garantia.cumplida else "ERROR",
        garantia="cumplida" if garantia.cumplida else "no_cumplida",
        fallos=len(informe.fallos),
    )
    return garantia.codigo_salida


if __name__ == "__main__":
    sys.exit(main())
