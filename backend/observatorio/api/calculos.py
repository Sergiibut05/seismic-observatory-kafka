"""Cálculos puros de la API (feature 005): horas con cero, intervalos, comparación y mapa.

Sin acceso a la base ni al reloj: reciben filas ya leídas y devuelven estructuras JSON.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from observatorio.common.tiempo import iso_utc

MAPA_TOPE = 5000
DIAS_2025 = 365
_HORA = timedelta(hours=1)

BORDES_MAGNITUD = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
BORDES_PROFUNDIDAD = (0, 10, 30, 70, 150, 300, 500, 700)


def _hora_en_punto(instante: datetime) -> datetime:
    return instante.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def rellenar_horas(filas: Sequence[tuple[datetime, int]], desde: datetime, hasta: datetime) -> list[dict]:
    """Una ventana por cada hora UTC de `[desde, hasta)`, con 0 donde no hay eventos.

    La primera y la última pueden ser parciales si `desde`/`hasta` no son horas en punto.
    """
    por_hora = {_hora_en_punto(inicio): int(recuento) for inicio, recuento in filas}
    ventanas = []
    inicio = _hora_en_punto(desde)
    # `hasta` es exclusivo: 12:00:00.000 no abre la ventana de las 12.
    ultimo = _hora_en_punto(hasta - timedelta(microseconds=1))
    while inicio <= ultimo:
        ventanas.append({"inicio": iso_utc(inicio), "recuento": por_hora.get(inicio, 0)})
        inicio += _HORA
    return ventanas


def _numero(valor: int) -> str:
    return str(valor)


def armar_intervalos(
    filas: Sequence[tuple[int | None, int]], bordes: Sequence[int]
) -> tuple[list[dict], int, int]:
    """Intervalos fijos con ceros, `sin_valor` aparte y total.

    `filas` = `(width_bucket, recuento)`: 0 = por debajo del primer borde, `len(bordes)` = desde el
    último borde; `None` = valor nulo, que no cae en ningún intervalo ni se cuenta como 0.
    """
    recuentos = {cubo: int(n) for cubo, n in filas if cubo is not None}
    sin_valor = sum(int(n) for cubo, n in filas if cubo is None)
    intervalos = []
    for cubo in range(len(bordes) + 1):
        if cubo == 0:
            desde, hasta, etiqueta = None, bordes[0], f"< {_numero(bordes[0])}"
        elif cubo == len(bordes):
            desde, hasta, etiqueta = bordes[-1], None, f"≥ {_numero(bordes[-1])}"
        else:
            desde, hasta = bordes[cubo - 1], bordes[cubo]
            etiqueta = f"{_numero(desde)}–{_numero(hasta)}"
        intervalos.append({"desde": desde, "hasta": hasta, "etiqueta": etiqueta, "recuento": recuentos.get(cubo, 0)})
    total = sum(i["recuento"] for i in intervalos) + sin_valor
    return intervalos, sin_valor, total


def comparar(eventos_24h: int, eventos_2025: int | None, cargado: bool) -> tuple[dict, float | None]:
    """Bloque `historico_2025` y cociente. Sin histórico cargado, todo `None` (nunca un 0 inventado).

    El denominador son siempre 365 días, también los de cero eventos. Media 0 → cociente `None`.
    """
    if not cargado or eventos_2025 is None:
        return {"estado": "no_cargado", "eventos": None, "dias": DIAS_2025, "media_diaria": None}, None
    media = eventos_2025 / DIAS_2025
    cociente = round(eventos_24h / media, 2) if media > 0 else None
    return {
        "estado": "cargado",
        "eventos": eventos_2025,
        "dias": DIAS_2025,
        "media_diaria": round(media, 4),
    }, cociente


def reproducido_en(ingested_at: datetime | None, modo: str) -> str | None:
    """Tiempo de reproducción: `ingested_at` solo en replay; en live es la ingesta y se informa `None`."""
    if modo != "replay" or ingested_at is None:
        return None
    return iso_utc(ingested_at)


def geojson_mapa(
    filas: Sequence[tuple], total: int, limite: int, generado: datetime, modo: str = "live"
) -> dict:
    """`FeatureCollection` para Leaflet; `[lon, lat]`; `truncado` si hay más eventos que el tope.

    `filas` = `(event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud, pais_nombre,
    sintetico, ingested_at)`.
    """
    if modo not in ("live", "replay"):
        raise ValueError("modo")
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [longitud, latitud]},
            "properties": {
                "event_id": event_id,
                "ocurrencia": iso_utc(ocurrencia),
                "updated": iso_utc(updated),
                "magnitud": magnitud,
                "profundidad": profundidad,
                "pais_nombre": pais_nombre,
                "sintetico": bool(sintetico),
                "reproducido_en": reproducido_en(ingested_at, modo),
            },
        }
        for (
            event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud,
            pais_nombre, sintetico, ingested_at,
        ) in filas[:limite]
    ]
    # Dos consultas no son atómicas: el total nunca puede quedar por debajo de lo devuelto.
    total = max(total, len(features))
    return {
        "type": "FeatureCollection",
        "modo": modo,
        "features": features,
        "total": total,
        "devueltos": len(features),
        "limite": limite,
        "truncado": total > len(features),
        "generated_at": iso_utc(generado),
    }


def desactualizado(ultima_ingesta: datetime | None, ahora: datetime, umbral_segundos: int) -> bool:
    """`True` sin ninguna ingesta correcta o si la última supera el umbral (en el umbral exacto, no)."""
    if ultima_ingesta is None:
        return True
    return (ahora - ultima_ingesta).total_seconds() > umbral_segundos
