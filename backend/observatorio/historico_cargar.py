"""Carga del histórico USGS 2025 en `historico.evento_2025` (feature 005).

Lee `HISTORICO_DIR/2025/eventos.geojson`, valida cada evento con las reglas del consumidor,
asigna país por punto en polígono y hace un upsert idempotente: solo un `updated` estrictamente
posterior sustituye la fila. Lo inservible o fuera de 2025 no se carga: se cuenta y se registra.
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from observatorio.common.catalogo import CatalogoError, IndicePaises, construir_indice
from observatorio.common.config import ajustes_productor, cargar_o_salir
from observatorio.common.contrato import Rechazo
from observatorio.common.db import Database, SinConexion
from observatorio.common.logging import configurar_logging, registrar
from observatorio.common.retry import motivo_de
from observatorio.common.tiempo import ms_a_datetime
from observatorio.consumer.calidad import Contenido, evaluar

_log = logging.getLogger("observatorio.historico_cargar")

INICIO_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
FIN_2025 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_UPDATED_MAXIMO_MS = 4_102_444_800_000  # 2100-01-01 UTC, el mismo tope que el contrato
TAMANO_LOTE = 1000

# Mismo esquema que db/init/005_historico.sql; aquí se repite para volúmenes antiguos.
_DDL = (
    "CREATE SCHEMA IF NOT EXISTS historico",
    """
    CREATE TABLE IF NOT EXISTS ingesta.pais (
        codigo      text PRIMARY KEY CHECK (codigo <> ''),
        nombre      text NOT NULL,
        continente  text,
        subregion   text
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS historico.evento_2025 (
        event_id     text             NOT NULL CHECK (event_id <> ''),
        updated      timestamptz      NOT NULL,
        ocurrencia   timestamptz      NOT NULL,
        magnitud     double precision,
        profundidad  double precision,
        longitud     double precision NOT NULL,
        latitud      double precision NOT NULL,
        pais_codigo  text,
        pais_nombre  text             NOT NULL,
        cargado_en   timestamptz      NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT evento_2025_pk PRIMARY KEY (event_id),
        CONSTRAINT evento_2025_ocurrencia_en_2025 CHECK (
            ocurrencia >= '2025-01-01T00:00:00Z' AND ocurrencia < '2026-01-01T00:00:00Z'),
        CONSTRAINT evento_2025_pais_fk FOREIGN KEY (pais_codigo) REFERENCES ingesta.pais (codigo)
    )
    """,
    "COMMENT ON TABLE historico.evento_2025 IS "
    "'Catálogo USGS de 2025 (solo datos reales), una fila por event_id con el updated más reciente. "
    "Denominador de la comparación histórica.'",
    "COMMENT ON COLUMN historico.evento_2025.ocurrencia IS "
    "'properties.time (ms epoch) en UTC; el CHECK la limita a 2025, así el denominador son siempre 365 días.'",
    "COMMENT ON COLUMN historico.evento_2025.updated IS "
    "'properties.updated (ms epoch) en UTC; solo una revisión estrictamente posterior sustituye la fila.'",
    "COMMENT ON COLUMN historico.evento_2025.magnitud IS 'Nulo si USGS no la informa; nunca se rellena con 0.'",
    "COMMENT ON COLUMN historico.evento_2025.profundidad IS 'Kilómetros, tercera coordenada del punto; nulo si falta.'",
    "COMMENT ON COLUMN historico.evento_2025.pais_codigo IS "
    "'ADM0_A3 por punto en polígono (EPSG:4326); nulo = «Sin país asignado».'",
    "COMMENT ON COLUMN historico.evento_2025.cargado_en IS 'Instante de la carga o de la última revisión aplicada.'",
    "CREATE INDEX IF NOT EXISTS evento_actual_ocurrencia_idx ON live.evento_actual (ocurrencia DESC, event_id)",
    "INSERT INTO ingesta.version_esquema (version, nombre) VALUES (5, 'historico') ON CONFLICT (version) DO NOTHING",
)

_UPSERT_PAIS = (
    "INSERT INTO ingesta.pais (codigo, nombre, continente, subregion) VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (codigo) DO NOTHING"
)

# Misma regla que el estado actual del consumidor: solo gana un `updated` estrictamente posterior.
_UPSERT = """
INSERT INTO historico.evento_2025 (
    event_id, updated, ocurrencia, magnitud, profundidad, longitud, latitud, pais_codigo, pais_nombre
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO UPDATE SET
    updated = EXCLUDED.updated,
    ocurrencia = EXCLUDED.ocurrencia,
    magnitud = EXCLUDED.magnitud,
    profundidad = EXCLUDED.profundidad,
    longitud = EXCLUDED.longitud,
    latitud = EXCLUDED.latitud,
    pais_codigo = EXCLUDED.pais_codigo,
    pais_nombre = EXCLUDED.pais_nombre,
    cargado_en = clock_timestamp()
WHERE historico.evento_2025.updated < EXCLUDED.updated
"""


@dataclass(frozen=True)
class FilaHistorica:
    event_id: str
    updated: datetime
    ocurrencia: datetime
    magnitud: float | None
    profundidad: float | None
    longitud: float
    latitud: float
    pais_codigo: str | None
    pais_nombre: str

    def parametros(self) -> tuple:
        return (
            self.event_id,
            self.updated,
            self.ocurrencia,
            self.magnitud,
            self.profundidad,
            self.longitud,
            self.latitud,
            self.pais_codigo,
            self.pais_nombre,
        )


def fila_desde_feature(feature, indice: IndicePaises) -> FilaHistorica | Rechazo:
    """Convierte un feature GeoJSON de USGS en una fila, o devuelve el rechazo con su motivo."""
    evento_id = feature.get("id") if isinstance(feature, dict) else None
    if not isinstance(evento_id, str) or not evento_id:
        return Rechazo("evento_sin_id", "event.id")
    contenido = evaluar({"event": feature})
    if not isinstance(contenido, Contenido):
        return Rechazo(contenido.motivo, contenido.detalle, evento_id)
    actualizado = feature["properties"].get("updated")
    if isinstance(actualizado, bool) or not isinstance(actualizado, int) or not 0 <= actualizado <= _UPDATED_MAXIMO_MS:
        return Rechazo("updated_invalido", "event.properties.updated", evento_id)
    if not INICIO_2025 <= contenido.ocurrencia < FIN_2025:
        return Rechazo("fuera_de_2025", f"ocurrencia_ms={contenido.ocurrencia_ms}", evento_id, actualizado)
    codigo, nombre = indice.asignar(contenido.longitud, contenido.latitud)
    return FilaHistorica(
        event_id=evento_id,
        updated=ms_a_datetime(actualizado),
        ocurrencia=contenido.ocurrencia,
        magnitud=contenido.magnitud,
        profundidad=contenido.profundidad,
        longitud=contenido.longitud,
        latitud=contenido.latitud,
        pais_codigo=codigo,
        pais_nombre=nombre,
    )


def preparar(features: list, indice: IndicePaises) -> tuple[list[FilaHistorica], list[Rechazo]]:
    filas: list[FilaHistorica] = []
    rechazos: list[Rechazo] = []
    for feature in features:
        resultado = fila_desde_feature(feature, indice)
        if isinstance(resultado, Rechazo):
            rechazos.append(resultado)
        else:
            filas.append(resultado)
    return filas, rechazos


def leer_features(ruta: Path) -> list:
    if not ruta.is_file():
        raise FileNotFoundError(f"no está el histórico: {ruta}. Ejecuta python -m observatorio.historico")
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    features = documento.get("features") if isinstance(documento, dict) else None
    if not isinstance(features, list):
        raise ValueError(f"{ruta} no tiene la lista «features»")
    return features


async def cargar(db: Database, filas: list[FilaHistorica], indice: IndicePaises, lote: int = TAMANO_LOTE) -> tuple[int, int]:
    """Esquema, países y upsert por lotes en UNA transacción. Devuelve (cargadas, omitidas).

    Omitida = ya existía con el mismo `updated` o con uno más reciente. Si algo falla,
    la transacción entera se deshace y no queda una carga parcial.
    """
    cargadas = 0
    async with db.transaccion(timeout=300) as conn:
        for sentencia in _DDL:
            await conn.execute(sentencia)
        for fila in indice.filas():
            await conn.execute(_UPSERT_PAIS, fila)
        for inicio in range(0, len(filas), lote):
            grupo = filas[inicio : inicio + lote]
            async with conn.cursor() as cursor:
                await cursor.executemany(_UPSERT, [fila.parametros() for fila in grupo])
                aplicadas = cursor.rowcount
            cargadas += aplicadas
            registrar(
                _log,
                "persistido",
                lote=inicio // lote + 1,
                filas=len(grupo),
                cargadas=aplicadas,
                omitidas=len(grupo) - aplicadas,
            )
    return cargadas, len(filas) - cargadas


async def _ejecutar(ajustes, ruta: Path, ruta_catalogo: str, espera_conexion: float) -> int:
    inicio = time.monotonic()
    registrar(_log, "iniciado", fichero=str(ruta), catalogo=ruta_catalogo)
    try:
        features = leer_features(ruta)
        indice = construir_indice(ruta_catalogo)
    except (FileNotFoundError, ValueError, OSError) as exc:
        registrar(_log, "error", nivel="ERROR", motivo="historico_ilegible", detalle=str(exc))
        return 1
    except CatalogoError as exc:
        registrar(_log, "error", nivel="ERROR", motivo=exc.motivo, detalle=exc.detalle)
        return 1

    filas, rechazos = preparar(features, indice)
    por_motivo = Counter(rechazo.motivo for rechazo in rechazos)
    for rechazo in rechazos:
        registrar(
            _log,
            "rechazado",
            nivel="WARNING",
            event_id=rechazo.event_id,
            updated=rechazo.updated,
            motivo=rechazo.motivo,
            detalle=rechazo.detalle,
        )

    db = Database.desde_ajustes(ajustes.postgres, ajustes.backoff)
    try:
        await asyncio.wait_for(db.conectar(), espera_conexion)
        cargadas, omitidas = await cargar(db, filas, indice)
        total = (await db.consultar("SELECT count(*) FROM historico.evento_2025", timeout=30))[0][0]
    except (TimeoutError, SinConexion, OSError, psycopg.OperationalError, psycopg.InterfaceError) as exc:
        registrar(_log, "error", nivel="ERROR", motivo="postgres_no_disponible", reason=motivo_de(exc))
        return 1
    except Exception as exc:
        registrar(_log, "error", nivel="ERROR", motivo="carga_fallida", reason=motivo_de(exc))
        return 1
    finally:
        await db.cerrar()

    sin_pais = sum(1 for fila in filas if fila.pais_codigo is None)
    registrar(
        _log,
        "listo",
        leidos=len(features),
        cargados=cargadas,
        omitidos=omitidas,
        rechazados=len(rechazos),
        rechazados_por_motivo=",".join(f"{motivo}:{n}" for motivo, n in sorted(por_motivo.items())) or "-",
        sin_pais=sin_pais,
        filas_tabla=total,
        segundos=round(time.monotonic() - inicio, 2),
    )
    return 0


def main() -> int:
    ajustes = cargar_o_salir("historico_cargar", ajustes_productor)
    configurar_logging("historico_cargar", ajustes.log_level, ajustes.secretos())
    directorio = Path(os.environ.get("HISTORICO_DIR", "/data/historico"))
    ruta_catalogo = os.environ.get("CATALOGO_PATH", "/catalogo/paises.geojson")
    try:
        espera = float(os.environ.get("HISTORICO_CONEXION_SEGUNDOS", "30"))
    except ValueError:
        espera = 30.0
    return asyncio.run(_ejecutar(ajustes, directorio / "2025" / "eventos.geojson", ruta_catalogo, espera))


if __name__ == "__main__":
    sys.exit(main())
