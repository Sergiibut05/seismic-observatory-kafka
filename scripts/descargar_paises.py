"""Descarga y valida el catálogo de países de Natural Earth (Admin 0, 1:50m).

Uso, desde la raíz del repositorio:

    python scripts/descargar_paises.py

Genera dos ficheros versionados en Git:

- ``catalogo/paises.geojson``: las mismas geometrías que la fuente, con solo
  los atributos que usa el proyecto. Lo lee el consumidor (punto en polígono)
  y lo sirve el panel Angular (fronteras del mapa).
- ``catalogo/paises.manifest.json``: procedencia, fecha de extracción, huellas
  SHA-256 de la fuente y del resultado, y resultado de cada comprobación.

La versión de Natural Earth está fijada por etiqueta para que dos ejecuciones
den el mismo fichero. Si alguna comprobación bloqueante falla, el script
termina con código 1 y no sobrescribe el catálogo existente.
"""

import argparse
import hashlib
import json
import math
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

NE_TAG = "v5.1.2"
NE_FILE = "ne_50m_admin_0_countries.geojson"
NE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    f"{NE_TAG}/geojson/{NE_FILE}"
)

# Atributos que se conservan. Los cinco primeros los exige el enunciado (4.3).
KEPT_FIELDS = [
    "ADM0_A3",
    "NAME_ES",
    "ADMIN",
    "CONTINENT",
    "SUBREGION",
    "REGION_UN",
    "ISO_A3",
    "TYPE",
]
REQUIRED_FIELDS = KEPT_FIELDS[:5]
ALLOWED_GEOMETRIES = {"Polygon", "MultiPolygon"}

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "catalogo"
OUT_GEOJSON = OUT_DIR / "paises.geojson"
OUT_MANIFEST = OUT_DIR / "paises.manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "seismic-observatory/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def iter_positions(geometry: dict):
    """Recorre todas las posiciones [lon, lat] de un Polygon o MultiPolygon."""
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    for polygon in polygons:
        for ring in polygon:
            yield from ring


def check_crs(collection: dict) -> dict:
    """GeoJSON RFC 7946 es WGS84 por definición; una declaración distinta es un error."""
    crs = collection.get("crs")
    name = (crs or {}).get("properties", {}).get("name", "")
    ok = crs is None or name.endswith("CRS84") or name.endswith("4326")
    return {"ok": ok, "declared": name or "ninguno (RFC 7946: WGS84)"}


def check_features(features: list) -> dict:
    missing = Counter()
    bad_geometry = []
    out_of_range = []
    for index, feature in enumerate(features):
        props = feature.get("properties") or {}
        for field in REQUIRED_FIELDS:
            if props.get(field) in (None, ""):
                missing[field] += 1
        geometry = feature.get("geometry") or {}
        code = props.get("ADM0_A3", f"#{index}")
        if geometry.get("type") not in ALLOWED_GEOMETRIES:
            bad_geometry.append(code)
            continue
        for lon, lat, *_ in iter_positions(geometry):
            finite = math.isfinite(lon) and math.isfinite(lat)
            if not finite or not (-180 <= lon <= 180 and -90 <= lat <= 90):
                out_of_range.append(code)
                break
    return {
        "missing_required": dict(missing),
        "non_polygon_geometries": bad_geometry,
        "coordinates_out_of_range": out_of_range,
    }


def check_uniqueness(features: list) -> dict:
    counts = Counter(f["properties"].get("ADM0_A3") for f in features)
    duplicates = sorted(code for code, n in counts.items() if n > 1)
    iso_mismatch = sorted(
        f["properties"]["ADM0_A3"]
        for f in features
        if f["properties"].get("ISO_A3") != f["properties"].get("ADM0_A3")
    )
    return {
        "adm0_a3_unique": not duplicates,
        "adm0_a3_duplicates": duplicates,
        # Informativo: ADM0_A3 no siempre coincide con ISO 3166-1 alfa-3.
        "adm0_a3_distinct_from_iso_a3": iso_mismatch,
    }


def check_validity_with_shapely(features: list) -> dict:
    """Validez topológica. Opcional: solo si Shapely está instalado."""
    try:
        from shapely.geometry import shape
        from shapely.validation import explain_validity
    except ImportError:
        return {"checked": False, "reason": "shapely no instalado"}
    invalid = {}
    for feature in features:
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            invalid[feature["properties"]["ADM0_A3"]] = explain_validity(geometry)
    return {"checked": True, "invalid": invalid}


def trim(feature: dict) -> dict:
    props = feature["properties"]
    return {
        "type": "Feature",
        "properties": {field: props.get(field) for field in KEPT_FIELDS},
        "geometry": feature["geometry"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        help="Fichero local de Natural Earth en vez de descargarlo",
    )
    args = parser.parse_args()

    raw = args.source.read_bytes() if args.source else download(NE_URL)
    collection = json.loads(raw)
    features = collection.get("features", [])

    checks = {
        "feature_count": len(features),
        "crs": check_crs(collection),
        "features": check_features(features),
        "uniqueness": check_uniqueness(features),
        "validity": check_validity_with_shapely(features),
    }
    blocking = [
        collection.get("type") != "FeatureCollection",
        not features,
        not checks["crs"]["ok"],
        bool(checks["features"]["missing_required"]),
        bool(checks["features"]["non_polygon_geometries"]),
        bool(checks["features"]["coordinates_out_of_range"]),
        not checks["uniqueness"]["adm0_a3_unique"],
    ]

    print(json.dumps(checks, indent=2, ensure_ascii=False))
    if any(blocking):
        print("ERROR: el catálogo no supera las comprobaciones; no se escribe nada.", file=sys.stderr)
        return 1

    output = {
        "type": "FeatureCollection",
        "features": [trim(f) for f in features],
    }
    encoded = json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    OUT_DIR.mkdir(exist_ok=True)
    OUT_GEOJSON.write_bytes(encoded)
    manifest = {
        "source": {
            "name": "Natural Earth Admin 0 – Countries 1:50m",
            "url": NE_URL if not args.source else str(args.source),
            "tag": NE_TAG,
            "sha256": sha256(raw),
            "bytes": len(raw),
        },
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "transformation": (
            "Se conservan geometrías y orden de la fuente sin modificar; "
            f"solo se eliminan atributos distintos de {KEPT_FIELDS}."
        ),
        "output": {
            "path": OUT_GEOJSON.relative_to(ROOT).as_posix(),
            "sha256": sha256(encoded),
            "bytes": len(encoded),
            "crs": "EPSG:4326 (WGS84, RFC 7946)",
            "fields": KEPT_FIELDS,
            "key": "ADM0_A3",
        },
        "checks": checks,
    }
    OUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"OK: {len(features)} países -> {OUT_GEOJSON.relative_to(ROOT)} ({len(encoded)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
