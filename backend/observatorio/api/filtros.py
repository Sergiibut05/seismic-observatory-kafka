"""Filtros comunes de la API (feature 005, FR-008): validación y WHERE parametrizado.

Módulo puro, sin acceso a la base. El texto que llega del usuario nunca se concatena en el SQL:
`construir_where` solo une fragmentos constantes con marcadores `%s` y devuelve los valores aparte.
"""

import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from observatorio.common.catalogo import SIN_PAIS

PARAMS_FILTRO = frozenset(
    {"desde", "hasta", "magnitud_min", "magnitud_max", "pais", "subregion", "incluir_sinteticos", "modo"}
)
PARAMS_LISTA = PARAMS_FILTRO | {"limite", "desplazamiento"}
# La ventana de la comparación es fija (24 h) y sus datos son siempre reales. Admite `modo` solo
# para poder rechazar `replay` con un 400 que nombre el parámetro (contrato 0.3.0).
PARAMS_COMPARACION = frozenset({"magnitud_min", "magnitud_max", "pais", "subregion", "modo"})

MODOS = ("live", "replay")

LIMITE_DEFECTO = 100
LIMITE_MAXIMO = 500
DESPLAZAMIENTO_MAXIMO = 100_000
MAGNITUD_TOPE = 10.0
SUBREGION_LARGO_MAX = 80
VENTANA_DEFECTO = timedelta(hours=24)
VENTANA_MAXIMA = timedelta(days=31)

_NUMERO = re.compile(r"^-?\d+(\.\d+)?$")
_ENTERO = re.compile(r"^\d{1,9}$")
_PAIS = re.compile(r"^[A-Z]{3}$")


class FiltroInvalido(Exception):
    """Parámetro de consulta mal formado. Solo guarda el nombre: el valor no se devuelve ni se registra."""

    def __init__(self, parametro: str):
        super().__init__(parametro)
        self.parametro = parametro


@dataclass(frozen=True)
class Filtros:
    desde: datetime | None = None
    hasta: datetime | None = None
    magnitud_min: float | None = None
    magnitud_max: float | None = None
    pais: str | None = None
    subregion: str | None = None
    incluir_sinteticos: bool = False
    # Solo selecciona la tabla (diccionario cerrado en `consultas.TABLAS`); nunca entra en el WHERE.
    modo: str = "live"


def valores_unicos(pares: Iterable[tuple[str, str]], permitidos: frozenset[str]) -> dict[str, str]:
    """Convierte los pares de la consulta en un diccionario; desconocido o repetido → `FiltroInvalido`."""
    valores: dict[str, str] = {}
    for nombre, valor in pares:
        if nombre not in permitidos or nombre in valores:
            raise FiltroInvalido(nombre if len(nombre) <= 40 and nombre.isidentifier() else "desconocido")
        valores[nombre] = valor
    return valores


def _instante(nombre: str, texto: str) -> datetime:
    try:
        instante = datetime.fromisoformat(texto)
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError("sin zona horaria")
        return instante.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise FiltroInvalido(nombre) from None


def _magnitud(nombre: str, texto: str) -> float:
    if not _NUMERO.fullmatch(texto):
        raise FiltroInvalido(nombre)
    valor = float(texto)
    if not math.isfinite(valor) or abs(valor) > MAGNITUD_TOPE:
        raise FiltroInvalido(nombre)
    return valor


def _texto_subregion(texto: str) -> str:
    if not texto or len(texto) > SUBREGION_LARGO_MAX or any(unicodedata.category(c) == "Cc" for c in texto):
        raise FiltroInvalido("subregion")
    return texto


def leer_filtros(valores: dict[str, str]) -> Filtros:
    """Valida los filtros presentes en `valores` (ya sin desconocidos ni repetidos)."""
    desde = _instante("desde", valores["desde"]) if "desde" in valores else None
    hasta = _instante("hasta", valores["hasta"]) if "hasta" in valores else None
    if desde is not None and hasta is not None and not desde < hasta:
        raise FiltroInvalido("hasta")
    magnitud_min = _magnitud("magnitud_min", valores["magnitud_min"]) if "magnitud_min" in valores else None
    magnitud_max = _magnitud("magnitud_max", valores["magnitud_max"]) if "magnitud_max" in valores else None
    if magnitud_min is not None and magnitud_max is not None and magnitud_min > magnitud_max:
        raise FiltroInvalido("magnitud_max")
    pais = valores.get("pais")
    if pais is not None and pais != SIN_PAIS and not _PAIS.fullmatch(pais):
        raise FiltroInvalido("pais")
    subregion = _texto_subregion(valores["subregion"]) if "subregion" in valores else None
    sinteticos = valores.get("incluir_sinteticos", "false")
    if sinteticos not in ("true", "false"):
        raise FiltroInvalido("incluir_sinteticos")
    modo = valores.get("modo", "live")
    if modo not in MODOS:
        raise FiltroInvalido("modo")
    return Filtros(desde, hasta, magnitud_min, magnitud_max, pais, subregion, sinteticos == "true", modo)


def leer_paginacion(valores: dict[str, str]) -> tuple[int, int]:
    """`limite` 1-500 (defecto 100) y `desplazamiento` 0-100.000 (defecto 0)."""
    limite = LIMITE_DEFECTO
    if "limite" in valores:
        if not _ENTERO.fullmatch(valores["limite"]) or not 1 <= int(valores["limite"]) <= LIMITE_MAXIMO:
            raise FiltroInvalido("limite")
        limite = int(valores["limite"])
    desplazamiento = 0
    if "desplazamiento" in valores:
        texto = valores["desplazamiento"]
        if not _ENTERO.fullmatch(texto) or int(texto) > DESPLAZAMIENTO_MAXIMO:
            raise FiltroInvalido("desplazamiento")
        desplazamiento = int(texto)
    return limite, desplazamiento


def leer_ventana(filtros: Filtros, ahora: datetime, ancla: datetime | None = None) -> Filtros:
    """Fija `desde`/`hasta` para los recuentos por hora (sin ninguno: últimas 24 h; máximo 31 días).

    Solo `desde` llega hasta el final por defecto; solo `hasta` retrocede 24 h. El final por defecto
    es `ahora`, o `ancla` si se da (replay: el último `ocurrencia`, porque sus eventos no son de hoy).
    """
    desde, hasta = filtros.desde, filtros.hasta
    fin = ancla if ancla is not None else ahora
    if desde is None and hasta is None:
        hasta = fin
        desde = fin - VENTANA_DEFECTO
    elif desde is None:
        desde = hasta - VENTANA_DEFECTO
    elif hasta is None:
        hasta = fin
    if not desde < hasta:
        raise FiltroInvalido("desde")
    if hasta - desde > VENTANA_MAXIMA:
        raise FiltroInvalido("hasta")
    return replace(filtros, desde=desde, hasta=hasta)


def construir_where(
    filtros: Filtros, *, fechas: bool = True, sinteticos: bool = True
) -> tuple[str, list]:
    """Devuelve `(" WHERE …" o "", parametros)`. Los fragmentos son constantes; los valores, `%s`.

    `fechas=False` ignora `desde`/`hasta` (comparación). `sinteticos=False` omite la regla de
    sintéticos (la tabla del histórico 2025 no tiene esa columna: todo es real).
    """
    condiciones: list[str] = []
    params: list = []
    if fechas and filtros.desde is not None:
        condiciones.append("ocurrencia >= %s")
        params.append(filtros.desde)
    if fechas and filtros.hasta is not None:
        condiciones.append("ocurrencia < %s")
        params.append(filtros.hasta)
    # Con filtro de magnitud, la magnitud nula queda fuera (la comparación con NULL no es verdadera).
    if filtros.magnitud_min is not None:
        condiciones.append("magnitud >= %s")
        params.append(filtros.magnitud_min)
    if filtros.magnitud_max is not None:
        condiciones.append("magnitud <= %s")
        params.append(filtros.magnitud_max)
    if filtros.pais == SIN_PAIS:
        condiciones.append("pais_codigo IS NULL")
    elif filtros.pais is not None:
        condiciones.append("pais_codigo = %s")
        params.append(filtros.pais)
    if filtros.subregion == SIN_PAIS:
        condiciones.append("pais_codigo IS NULL")
    elif filtros.subregion is not None:
        condiciones.append("pais_codigo IN (SELECT sr.codigo FROM ingesta.pais sr WHERE sr.subregion = %s)")
        params.append(filtros.subregion)
    if sinteticos and not filtros.incluir_sinteticos:
        condiciones.append("NOT sintetico")
    if not condiciones:
        return "", params
    return " WHERE " + " AND ".join(condiciones), params
