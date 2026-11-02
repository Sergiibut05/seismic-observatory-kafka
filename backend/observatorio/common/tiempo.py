"""Conversión de instantes: todo se guarda y se muestra en UTC."""

from datetime import datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def ms_a_datetime(ms: int) -> datetime:
    """Milisegundos epoch (USGS) a `datetime` UTC con aritmética entera, sin pasar por `float`."""
    return EPOCH + timedelta(milliseconds=ms)


def iso_utc(instante: datetime) -> str:
    """ISO 8601 en UTC con milisegundos y `Z` (convención de docs/CONTRATO-API.md)."""
    utc = instante.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
