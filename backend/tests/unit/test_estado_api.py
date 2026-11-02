"""Pruebas de `armar_estado` y `consultar_estado` (FR-023, FR-007 de la 005, contracts/api.openapi.yaml)."""

import asyncio
import re
from datetime import datetime, timedelta, timezone

import pytest

from observatorio.api.estado import armar_estado, consultar_estado, iso_utc
from observatorio.common.db import SinConexion

AHORA = datetime(2026, 11, 2, 12, 0, 5, tzinfo=timezone.utc)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

# Campos de la 0.1.0 (intactos) y los añadidos en la 0.2.0.
CLAVES_0_1 = {"base_de_datos", "eventos_reales", "eventos_sinteticos", "ultimo_evento", "generated_at"}
CLAVES_NUEVAS = {
    "ultima_ingesta_correcta",
    "periodo_consultado",
    "datos_desactualizados",
    "umbral_datos_desactualizados_segundos",
}
CLAVES = CLAVES_0_1 | CLAVES_NUEVAS
CLAVES_ULTIMO = {"event_id", "updated", "source", "sintetico", "processed_at"}

INGESTA = AHORA - timedelta(seconds=40)
PERIODO = (datetime(2026, 10, 1, 3, 4, 5, 6000, tzinfo=timezone.utc), datetime(2026, 11, 2, 11, 59, tzinfo=timezone.utc))


def ultimo(**cambios):
    fila = {
        "event_id": "synthetic-smoke-0001",
        "updated": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "source": "synthetic-smoke",
        "sintetico": True,
        "processed_at": datetime(2026, 11, 2, 12, 0, 0, 456000, tzinfo=timezone.utc),
    }
    fila.update(cambios)
    return (fila["event_id"], fila["updated"], fila["source"], fila["sintetico"], fila["processed_at"])


def test_base_conectada_con_eventos():
    estado = armar_estado((0, 1), ultimo(), True, AHORA)
    assert set(estado) == CLAVES
    assert estado["base_de_datos"] == "conectada"
    assert estado["eventos_reales"] == 0 and isinstance(estado["eventos_reales"], int)
    assert estado["eventos_sinteticos"] == 1
    assert set(estado["ultimo_evento"]) == CLAVES_ULTIMO
    assert estado["ultimo_evento"]["event_id"] == "synthetic-smoke-0001"
    assert estado["ultimo_evento"]["source"] == "synthetic-smoke"
    assert estado["ultimo_evento"]["sintetico"] is True


def test_los_instantes_van_en_iso_utc_con_z_y_milisegundos():
    estado = armar_estado((0, 1), ultimo(), True, AHORA, INGESTA, PERIODO)
    assert estado["generated_at"] == "2026-11-02T12:00:05.000Z"
    assert estado["ultimo_evento"]["updated"] == "2026-01-01T00:00:00.000Z"
    assert estado["ultimo_evento"]["processed_at"] == "2026-11-02T12:00:00.456Z"
    assert estado["ultima_ingesta_correcta"] == "2026-11-02T11:59:25.000Z"
    assert estado["periodo_consultado"] == {"desde": "2026-10-01T03:04:05.006Z", "hasta": "2026-11-02T11:59:00.000Z"}
    for valor in (
        estado["generated_at"],
        estado["ultimo_evento"]["updated"],
        estado["ultimo_evento"]["processed_at"],
        estado["ultima_ingesta_correcta"],
        *estado["periodo_consultado"].values(),
    ):
        assert ISO.match(valor)


def test_un_instante_con_otra_zona_se_convierte_a_utc():
    madrid = timezone(timedelta(hours=1))
    assert iso_utc(datetime(2026, 11, 2, 13, 0, 0, tzinfo=madrid)) == "2026-11-02T12:00:00.000Z"


def test_base_vacia():
    estado = armar_estado((0, 0), None, True, AHORA)
    assert estado["base_de_datos"] == "conectada"
    assert estado["eventos_reales"] == 0
    assert estado["eventos_sinteticos"] == 0
    assert estado["ultimo_evento"] is None


def test_base_caida_devuelve_none_nunca_cero():
    estado = armar_estado(None, None, False, AHORA)
    assert estado["base_de_datos"] == "fallida"
    assert estado["eventos_reales"] is None
    assert estado["eventos_sinteticos"] is None
    assert estado["ultimo_evento"] is None
    assert estado["ultima_ingesta_correcta"] is None
    assert estado["periodo_consultado"] is None
    assert estado["datos_desactualizados"] is None
    assert set(estado) == CLAVES


def test_base_caida_ignora_datos_residuales():
    # Aunque se pasaran datos, con la base caída el estado nunca debe mostrarlos como actuales.
    estado = armar_estado((5, 6), ultimo(), False, AHORA, INGESTA, PERIODO)
    assert estado["eventos_reales"] is None
    assert estado["eventos_sinteticos"] is None
    assert estado["ultimo_evento"] is None
    assert estado["ultima_ingesta_correcta"] is None
    assert estado["periodo_consultado"] is None
    assert estado["datos_desactualizados"] is None


def test_los_sinteticos_solo_se_suman_en_su_contador():
    estado = armar_estado((3, 2), ultimo(), True, AHORA)
    assert estado["eventos_reales"] == 3
    assert estado["eventos_sinteticos"] == 2


def test_ultimo_evento_real():
    fila = ultimo(event_id="us7000abcd", source="usgs", sintetico=False)
    estado = armar_estado((1, 0), fila, True, AHORA)
    assert estado["ultimo_evento"]["sintetico"] is False
    assert estado["ultimo_evento"]["source"] == "usgs"


# --- 0.2.0 (FR-007, AC-10) -------------------------------------------------


def test_ingesta_reciente_no_esta_desactualizado():
    estado = armar_estado((1, 0), None, True, AHORA, INGESTA, PERIODO, 300)
    assert estado["datos_desactualizados"] is False
    assert estado["umbral_datos_desactualizados_segundos"] == 300


def test_ingesta_fuera_del_umbral_esta_desactualizado():
    antigua = AHORA - timedelta(seconds=301)
    assert armar_estado((1, 0), None, True, AHORA, antigua, PERIODO, 300)["datos_desactualizados"] is True


def test_sin_ninguna_ingesta_correcta_esta_desactualizado_y_no_es_nulo():
    estado = armar_estado((0, 0), None, True, AHORA, None, None)
    assert estado["ultima_ingesta_correcta"] is None
    assert estado["datos_desactualizados"] is True


def test_sin_eventos_reales_el_periodo_es_nulo():
    estado = armar_estado((0, 1), ultimo(), True, AHORA, INGESTA, (None, None))
    assert estado["periodo_consultado"] is None


def test_el_umbral_se_informa_aunque_la_base_este_caida():
    assert armar_estado(None, None, False, AHORA, umbral_segundos=900)["umbral_datos_desactualizados_segundos"] == 900


# --- consultar_estado con una base falsa -----------------------------------


class BdFalsa:
    def __init__(self, respuestas=None, error=None):
        self.respuestas = respuestas or {}
        self.error = error

    async def consultar(self, sql, params=None, timeout=3.0):
        if self.error is not None:
            raise self.error
        for clave, filas in self.respuestas.items():
            if clave in sql:
                return filas
        raise AssertionError(f"consulta inesperada: {sql}")


def test_consultar_estado_con_la_base_caida_no_devuelve_ceros():
    estado = asyncio.run(consultar_estado(BdFalsa(error=SinConexion("x"))))
    assert estado["base_de_datos"] == "fallida"
    assert estado["eventos_reales"] is None and estado["ultima_ingesta_correcta"] is None
    assert estado["periodo_consultado"] is None and estado["datos_desactualizados"] is None


def test_consultar_estado_ante_un_error_inesperado_tambien_da_none():
    estado = asyncio.run(consultar_estado(BdFalsa(error=RuntimeError("boom"))))
    assert estado["base_de_datos"] == "fallida" and estado["eventos_reales"] is None


def test_consultar_estado_lee_ingesta_y_periodo():
    ahora = datetime.now(timezone.utc)
    bd = BdFalsa(
        {
            "count(*) FILTER": [(7, 1)],
            "ORDER BY processed_at": [],
            "FROM ingesta.consultas": [(ahora - timedelta(seconds=30),)],
            "min(ocurrencia)": [(ahora - timedelta(days=10), ahora - timedelta(minutes=5))],
        }
    )
    estado = asyncio.run(consultar_estado(bd, umbral_segundos=120))
    assert estado["base_de_datos"] == "conectada"
    assert estado["eventos_reales"] == 7 and estado["eventos_sinteticos"] == 1
    assert estado["datos_desactualizados"] is False
    assert estado["umbral_datos_desactualizados_segundos"] == 120
    assert ISO.match(estado["periodo_consultado"]["desde"])


def test_consultar_estado_sin_filas_de_ingesta_esta_desactualizado():
    bd = BdFalsa(
        {
            "count(*) FILTER": [(0, 0)],
            "ORDER BY processed_at": [],
            "FROM ingesta.consultas": [],
            "min(ocurrencia)": [(None, None)],
        }
    )
    estado = asyncio.run(consultar_estado(bd))
    assert estado["datos_desactualizados"] is True
    assert estado["ultima_ingesta_correcta"] is None and estado["periodo_consultado"] is None


@pytest.mark.parametrize("campo", sorted(CLAVES_0_1))
def test_los_campos_de_la_0_1_0_siguen_presentes(campo):
    assert campo in armar_estado((0, 0), None, True, AHORA)
