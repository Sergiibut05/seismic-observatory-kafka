"""Cargador de 2025: conversión de fila, rechazos con motivo, país por polígono e idempotencia."""

import asyncio
import contextlib
import json
from datetime import datetime, timezone

import pytest

from observatorio.common.catalogo import SIN_PAIS, construir_indice
from observatorio.common.contrato import Rechazo
from observatorio.historico_cargar import (
    _DDL,
    _UPSERT,
    FilaHistorica,
    cargar,
    fila_desde_feature,
    preparar,
)

T_2025 = 1_750_000_000_000  # 2025-06-15 UTC
INICIO_2025_MS = 1_735_689_600_000
FIN_2025_MS = 1_767_225_600_000


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    caja = {
        "type": "Polygon",
        "coordinates": [[[-10, 35], [5, 35], [5, 45], [-10, 45], [-10, 35]]],
    }
    catalogo = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ADM0_A3": "ESP", "NAME_ES": "España", "CONTINENT": "Europa", "SUBREGION": "Sur de Europa"},
                "geometry": caja,
            }
        ],
    }
    ruta = tmp_path_factory.mktemp("catalogo") / "paises.geojson"
    ruta.write_text(json.dumps(catalogo), encoding="utf-8")
    return construir_indice(ruta)


def feature(event_id="us1", time=T_2025, updated=None, mag=4.5, coordenadas=(-3.7, 40.4, 10.0), **extra):
    propiedades = {"time": time, "mag": mag, "place": "texto que no se usa para el país"}
    propiedades["updated"] = time + 1000 if updated is None else updated
    propiedades.update(extra)
    return {"type": "Feature", "id": event_id, "properties": propiedades, "geometry": {"type": "Point", "coordinates": list(coordenadas)}}


def test_fila_desde_feature_convierte_ms_a_utc_y_asigna_pais(indice):
    fila = fila_desde_feature(feature(time=T_2025 + 7, updated=T_2025 + 1007), indice)
    assert isinstance(fila, FilaHistorica)
    assert fila.event_id == "us1"
    assert fila.ocurrencia == datetime(2025, 6, 15, 15, 6, 40, 7000, tzinfo=timezone.utc)
    assert fila.updated == datetime(2025, 6, 15, 15, 6, 41, 7000, tzinfo=timezone.utc)
    assert (fila.longitud, fila.latitud, fila.profundidad, fila.magnitud) == (-3.7, 40.4, 10.0, 4.5)
    assert (fila.pais_codigo, fila.pais_nombre) == ("ESP", "España")


def test_punto_sin_poligono_queda_sin_pais_asignado(indice):
    fila = fila_desde_feature(feature(coordenadas=(150.0, -30.0, 5.0)), indice)
    assert isinstance(fila, FilaHistorica)
    assert fila.pais_codigo is None
    assert fila.pais_nombre == SIN_PAIS


def test_magnitud_y_profundidad_ausentes_siguen_nulas(indice):
    sin_datos = feature(mag=None, coordenadas=(-3.7, 40.4))
    fila = fila_desde_feature(sin_datos, indice)
    assert isinstance(fila, FilaHistorica)
    assert fila.magnitud is None and fila.profundidad is None


@pytest.mark.parametrize(
    "evento, motivo",
    [
        (feature(updated=None) | {"properties": {"time": T_2025, "mag": 3.0}}, "updated_invalido"),
        (feature(updated=1.5e12), "updated_invalido"),
        (feature(updated=True), "updated_invalido"),
        (feature(time="ayer", updated=T_2025), "tiempo_invalido"),
        (feature(time=INICIO_2025_MS - 1), "fuera_de_2025"),
        (feature(time=FIN_2025_MS), "fuera_de_2025"),
        (feature(event_id=""), "evento_sin_id"),
        (feature(coordenadas=(200.0, 10.0, 1.0)), "coordenadas_fuera_de_rango"),
        ({"id": "us9", "properties": {"time": T_2025, "updated": T_2025}, "geometry": None}, "geometria_inutilizable"),
    ],
)
def test_rechaza_con_motivo_y_sin_rellenar(indice, evento, motivo):
    resultado = fila_desde_feature(evento, indice)
    assert isinstance(resultado, Rechazo)
    assert resultado.motivo == motivo


def test_limites_de_2025_son_inicio_incluido_y_fin_excluido(indice):
    assert isinstance(fila_desde_feature(feature(time=INICIO_2025_MS, updated=INICIO_2025_MS), indice), FilaHistorica)
    ultimo = fila_desde_feature(feature(time=FIN_2025_MS - 1, updated=FIN_2025_MS - 1), indice)
    assert isinstance(ultimo, FilaHistorica)
    assert ultimo.ocurrencia == datetime(2025, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc)


def test_preparar_separa_filas_y_rechazos(indice):
    filas, rechazos = preparar([feature("a"), feature("b", time=0), feature("c", coordenadas=(150.0, -30.0))], indice)
    assert [fila.event_id for fila in filas] == ["a", "c"]
    assert [(r.event_id, r.motivo) for r in rechazos] == [("b", "fuera_de_2025")]


class _CursorFalso:
    def __init__(self, base):
        self._base = base
        self.rowcount = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *excepcion):
        return False

    async def executemany(self, sentencia, lote):
        assert sentencia == _UPSERT
        self.rowcount = sum(self._base.aplicar(parametros) for parametros in lote)


class _ConexionFalsa:
    def __init__(self, base):
        self._base = base
        self.sentencias = []

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append(sentencia)

    def cursor(self):
        return _CursorFalso(self._base)


class _BaseFalsa:
    """Imita `ON CONFLICT … WHERE updated < EXCLUDED.updated` sobre un diccionario."""

    def __init__(self):
        self.filas = {}
        self.transacciones = 0
        self.conexion = _ConexionFalsa(self)

    def aplicar(self, parametros) -> int:
        event_id, updated = parametros[0], parametros[1]
        if event_id in self.filas and not self.filas[event_id][1] < updated:
            return 0
        self.filas[event_id] = parametros
        return 1

    @contextlib.asynccontextmanager
    async def transaccion(self, timeout=10.0):
        self.transacciones += 1
        yield self.conexion


def test_cargar_es_idempotente_y_gana_el_updated_mas_reciente(indice):
    base = _BaseFalsa()
    filas, _ = preparar([feature("a"), feature("b", time=T_2025 + 5)], indice)

    primera = asyncio.run(cargar(base, filas, indice, lote=1))
    segunda = asyncio.run(cargar(base, filas, indice, lote=1))
    assert primera == (2, 0)
    assert segunda == (0, 2)
    assert len(base.filas) == 2

    revisada, _ = preparar([feature("a", updated=T_2025 + 60_000, mag=5.1)], indice)
    antigua, _ = preparar([feature("a", updated=T_2025 + 500, mag=1.0)], indice)
    assert asyncio.run(cargar(base, revisada, indice)) == (1, 0)
    assert asyncio.run(cargar(base, antigua, indice)) == (0, 1)
    assert base.filas["a"][3] == 5.1
    assert len(base.filas) == 2


def test_cargar_usa_una_transaccion_y_crea_esquema_antes_de_insertar(indice):
    base = _BaseFalsa()
    filas, _ = preparar([feature(f"e{n}", time=T_2025 + n) for n in range(5)], indice)
    asyncio.run(cargar(base, filas, indice, lote=2))
    assert base.transacciones == 1
    assert any("CREATE SCHEMA IF NOT EXISTS historico" in sentencia for sentencia in base.conexion.sentencias)


def test_ddl_define_clave_check_fk_y_el_indice_de_la_lista():
    ddl = "\n".join(_DDL)
    assert "PRIMARY KEY (event_id)" in ddl
    assert "ocurrencia < '2026-01-01T00:00:00Z'" in ddl
    assert "REFERENCES ingesta.pais (codigo)" in ddl
    assert "ON live.evento_actual (ocurrencia DESC, event_id)" in ddl
    assert "(5, 'historico')" in ddl
