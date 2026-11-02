"""Decisión pura del consumidor ante un registro Kafka (R-09, R-15): sin infraestructura."""

from dataclasses import dataclass

import psycopg

from observatorio.common.contrato import MensajeValido, validar_mensaje

# El esquema destino sale de esta lista cerrada (coincide con `mode`), nunca de texto libre.
ESQUEMAS_DESTINO = {"live": "live", "replay": "replay"}


@dataclass(frozen=True)
class Aceptar:
    version: MensajeValido
    esquema: str


@dataclass(frozen=True)
class Rechazar:
    motivo: str
    detalle: str = ""
    event_id: str | None = None
    updated: int | None = None


def decidir(registro, topic_modo: str) -> Aceptar | Rechazar:
    """`registro` solo necesita `key` y `value`. `topic_modo` es el modo del topic (`live`/`replay`)."""
    if topic_modo not in ESQUEMAS_DESTINO:
        raise ValueError(f"modo de topic desconocido: {topic_modo!r}")
    resultado = validar_mensaje(registro.key, registro.value, topic_modo)
    if isinstance(resultado, MensajeValido):
        return Aceptar(version=resultado, esquema=ESQUEMAS_DESTINO[resultado.mode])
    return Rechazar(resultado.motivo, resultado.detalle, resultado.event_id, resultado.updated)


def resultado_escritura(filas: int) -> str:
    """`INSERT … ON CONFLICT DO NOTHING`: 1 fila = persistido, 0 = versión ya existente."""
    if filas == 1:
        return "persistido"
    if filas == 0:
        return "omitido"
    raise ValueError(f"número de filas inesperado: {filas!r}")


def clasificar_error_bd(excepcion: BaseException) -> str:
    """«reintentar» (conexión), «cuarentena» (dato, SQLSTATE 22/23) o «desconocido» (se reintenta con error)."""
    if isinstance(excepcion, (psycopg.OperationalError, psycopg.InterfaceError)):
        return "reintentar"
    if isinstance(excepcion, (psycopg.DataError, psycopg.IntegrityError)):
        return "cuarentena"
    return "desconocido"
