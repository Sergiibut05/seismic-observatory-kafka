"""Plan de tramos del relleno: ninguna consulta pasa del tope de su fuente (FR-010, SC-005)."""

import bisect
from datetime import datetime, timedelta, timezone

import pytest

from observatorio.relleno import ErrorPlan, planificar, tramos_mensuales


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def contador(instantes):
    """`contar` falso: eventos en [desde, hasta) sobre una lista ordenada de instantes."""
    ordenados = sorted(instantes)
    llamadas = []

    def contar(desde, hasta):
        llamadas.append((desde, hasta))
        return bisect.bisect_left(ordenados, hasta) - bisect.bisect_left(ordenados, desde)

    return contar, llamadas


def test_meses_naturales_recortados():
    tramos = tramos_mensuales(utc(2025, 11, 15), utc(2026, 2, 10))
    assert tramos == [
        (utc(2025, 11, 15), utc(2025, 12, 1)),
        (utc(2025, 12, 1), utc(2026, 1, 1)),
        (utc(2026, 1, 1), utc(2026, 2, 1)),
        (utc(2026, 2, 1), utc(2026, 2, 10)),
    ]


def test_parte_hasta_que_cabe_sin_perder_ni_repetir_eventos():
    # 30.000 eventos repartidos en marzo de 2025 y un tope de 8.000 (EMSC).
    inicio = utc(2025, 3, 1)
    instantes = [inicio + timedelta(seconds=89 * i) for i in range(30_000)]
    contar, _ = contador(instantes)
    plan = planificar(utc(2025, 3, 1), utc(2025, 4, 1), contar, 8_000)
    assert all(t.eventos <= 8_000 for t in plan)
    assert sum(t.eventos for t in plan) == sum(1 for x in instantes if x < utc(2025, 4, 1))
    # Tramos contiguos y en orden.
    for anterior, siguiente in zip(plan, plan[1:]):
        assert anterior.hasta <= siguiente.desde


def test_los_tramos_vacios_no_se_piden():
    contar, _ = contador([utc(2025, 2, 10)])
    plan = planificar(utc(2025, 1, 1), utc(2025, 4, 1), contar, 100)
    assert [(t.desde, t.eventos) for t in plan] == [(utc(2025, 2, 1), 1)]


def test_un_tramo_minimo_que_no_cabe_es_un_error_y_no_un_truncado():
    momento = utc(2025, 3, 3, 12)
    contar, _ = contador([momento] * 50)  # 50 eventos en el mismo instante
    with pytest.raises(ErrorPlan):
        planificar(utc(2025, 3, 1), utc(2025, 4, 1), contar, 10)


def test_intervalo_invertido():
    with pytest.raises(ValueError):
        planificar(utc(2025, 4, 1), utc(2025, 3, 1), lambda a, b: 0, 10)
