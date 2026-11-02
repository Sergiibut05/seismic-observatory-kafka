"""Carga y validación del catálogo de países al arrancar el consumidor (R-18).

Solo se valida; las geometrías no se conservan en memoria (la asignación de país es de la 003).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import shape

MOTIVOS = (
    "catalogo_ausente",
    "catalogo_ilegible",
    "catalogo_vacio",
    "geometria_no_poligonal",
    "adm0_a3_ausente",
    "adm0_a3_repetido",
)

_TIPOS_POLIGONALES = ("Polygon", "MultiPolygon")


class CatalogoError(Exception):
    """Catálogo inválido con un motivo de lista cerrada y un detalle sin secretos."""

    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(f"{motivo}: {detalle}" if detalle else motivo)
        self.motivo = motivo
        self.detalle = detalle


@dataclass(frozen=True)
class Catalogo:
    total: int
    fuente: str
    geometrias_invalidas: int = 0


def _leer(ruta: Path) -> dict:
    try:
        texto = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CatalogoError("catalogo_ausente", f"no existe {ruta}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise CatalogoError("catalogo_ilegible", f"no se pudo leer {ruta}: {type(exc).__name__}") from None
    try:
        datos = json.loads(texto)
    except ValueError:
        raise CatalogoError("catalogo_ilegible", f"{ruta} no es JSON válido") from None
    if not isinstance(datos, dict) or datos.get("type") != "FeatureCollection":
        raise CatalogoError("catalogo_ilegible", f"{ruta} no es una FeatureCollection")
    if not isinstance(datos.get("features"), list):
        raise CatalogoError("catalogo_ilegible", f"{ruta} no tiene la lista «features»")
    return datos


def cargar_catalogo(ruta: str | Path) -> Catalogo:
    """Valida el GeoJSON de países y devuelve cuántos hay; lanza `CatalogoError` si no es válido."""
    ruta = Path(ruta)
    entidades = _leer(ruta)["features"]
    if not entidades:
        raise CatalogoError("catalogo_vacio", f"{ruta} no contiene entidades")

    codigos: set[str] = set()
    invalidas = 0
    for posicion, entidad in enumerate(entidades):
        propiedades = entidad.get("properties") if isinstance(entidad, dict) else None
        codigo = propiedades.get("ADM0_A3") if isinstance(propiedades, dict) else None
        if not isinstance(codigo, str) or not codigo:
            raise CatalogoError("adm0_a3_ausente", f"entidad en la posición {posicion}")
        geometria = entidad.get("geometry")
        if not isinstance(geometria, dict) or geometria.get("type") not in _TIPOS_POLIGONALES:
            tipo = geometria.get("type") if isinstance(geometria, dict) else None
            raise CatalogoError("geometria_no_poligonal", f"ADM0_A3={codigo} tipo={tipo}")
        if codigo in codigos:
            raise CatalogoError("adm0_a3_repetido", f"ADM0_A3={codigo}")
        codigos.add(codigo)
        try:
            if not shape(geometria).is_valid:
                invalidas += 1
        except Exception as exc:
            raise CatalogoError("catalogo_ilegible", f"geometría de {codigo}: {type(exc).__name__}") from None
    return Catalogo(total=len(entidades), fuente=str(ruta), geometrias_invalidas=invalidas)
