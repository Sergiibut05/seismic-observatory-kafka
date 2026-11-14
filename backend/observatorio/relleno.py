"""Relleno de la base con el histórico de las fuentes (feature 013, FR-010).

`python -m observatorio.relleno --desde 2025-01-01 [--hasta 2026-11-14T00:00:00] --magnitud-min 2.5
[--fuentes usgs,emsc]`

Publica en los topics por fuente (`eventos.usgs`, `eventos.emsc`) todos los terremotos del
intervalo, por tramos que caben en una consulta; desde ahí pasan por la misma fusión que el
directo. Marca lo publicado en `ingesta.publicadas`: repetirlo no republica nada.

Ninguna fuente avisa bien de que se pasa: USGS rechaza más de 20.000 filas y EMSC corta en
~10.000 sin decir nada. Por eso se cuenta antes (`/count`) y se parte el tramo hasta que cabe.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

TRAMO_MINIMO = timedelta(minutes=30)


class ErrorPlan(Exception):
    """Un tramo ya mínimo sigue sin caber en una consulta: no se puede rellenar sin truncar."""


@dataclass(frozen=True)
class Tramo:
    desde: datetime
    hasta: datetime
    eventos: int


def tramos_mensuales(desde: datetime, hasta: datetime) -> list[tuple[datetime, datetime]]:
    """Meses naturales (el primero y el último, recortados). El fin de uno es el inicio del siguiente."""
    tramos = []
    inicio = desde
    while inicio < hasta:
        siguiente_mes = (
            datetime(inicio.year + 1, 1, 1, tzinfo=timezone.utc)
            if inicio.month == 12
            else datetime(inicio.year, inicio.month + 1, 1, tzinfo=timezone.utc)
        )
        fin = min(siguiente_mes, hasta)
        tramos.append((inicio, fin))
        inicio = fin
    return tramos


def planificar(
    desde: datetime,
    hasta: datetime,
    contar: Callable[[datetime, datetime], int],
    tope: int,
    minimo: timedelta = TRAMO_MINIMO,
) -> list[Tramo]:
    """Tramos con como mucho `tope` eventos cada uno, en orden. Los vacíos no se incluyen.

    Empieza por meses y parte por la mitad mientras `contar` diga que no cabe. Lanza `ErrorPlan`
    si un tramo de `minimo` o menos sigue sin caber.
    """
    if not desde < hasta:
        raise ValueError("desde debe ser anterior a hasta")
    plan: list[Tramo] = []
    pendientes = list(reversed(tramos_mensuales(desde, hasta)))
    while pendientes:
        inicio, fin = pendientes.pop()
        eventos = contar(inicio, fin)
        if eventos <= tope:
            if eventos > 0:
                plan.append(Tramo(inicio, fin, eventos))
            continue
        if fin - inicio <= minimo:
            raise ErrorPlan(f"{inicio.isoformat()}–{fin.isoformat()} tiene {eventos} eventos (tope {tope})")
        medio = inicio + (fin - inicio) / 2
        pendientes.extend([(medio, fin), (inicio, medio)])  # se procesa antes la primera mitad
    return plan
