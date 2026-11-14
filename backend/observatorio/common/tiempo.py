"""Conversión de instantes: todo se guarda y se muestra en UTC."""

from datetime import datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def ms_a_datetime(ms: int) -> datetime:
    """Milisegundos epoch (USGS) a `datetime` UTC con aritmética entera, sin pasar por `float`."""
    return EPOCH + timedelta(milliseconds=ms)


def datetime_a_ms(instante: datetime) -> int:
    """`datetime` con zona a milisegundos epoch, con aritmética entera (trunca por debajo del ms)."""
    return (instante - EPOCH) // timedelta(milliseconds=1)


def iso_a_ms(texto) -> int | None:
    """ISO 8601 (`2026-11-13T23:58:30.0Z`, como EMSC) a ms epoch; `None` si no se puede leer.

    Sin zona se toma como UTC: el estándar FDSN da los instantes en UTC.
    """
    if not isinstance(texto, str) or not texto:
        return None
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return datetime_a_ms(instante)


def iso_utc(instante: datetime) -> str:
    """ISO 8601 en UTC con milisegundos y `Z` (convención de docs/CONTRATO-API.md)."""
    utc = instante.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
