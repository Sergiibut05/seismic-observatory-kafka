"""Descarga del catálogo USGS 2025 por intervalos, sin truncar y sin duplicar extremos."""

import json
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from observatorio.producer.feed import ErrorTransitorio, es_transitorio

LIMITE_USGS = 20_000
URL_BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
ANIO_DEFECTO = 2025


def meses(anio: int):
    """Doce intervalos [mes, mes siguiente). El fin de uno es el inicio del siguiente."""
    for mes in range(1, 13):
        inicio = datetime(anio, mes, 1, tzinfo=timezone.utc)
        fin = datetime(anio + 1, 1, 1, tzinfo=timezone.utc) if mes == 12 else datetime(anio, mes + 1, 1, tzinfo=timezone.utc)
        yield inicio, fin


def partir(inicio: datetime, fin: datetime) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    """Parte por la mitad. Falla si el intervalo ya no da dos trozos distintos."""
    medio = inicio + (fin - inicio) / 2
    if medio <= inicio or medio >= fin:
        raise ValueError("el intervalo no se puede partir más")
    return (inicio, medio), (medio, fin)


def url_consulta(inicio: datetime, fin: datetime, magnitud_minima: float = 4) -> str:
    parametros = {
        "format": "geojson",
        "starttime": inicio.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endtime": fin.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minmagnitude": magnitud_minima,
        "eventtype": "earthquake",
        "orderby": "time-asc",
    }
    return URL_BASE + "?" + urllib.parse.urlencode(parametros)


def es_exceso(status: int, cuerpo: bytes) -> bool:
    if status != 400:
        return False
    texto = cuerpo.lower()
    return b"20000" in texto or b"too large" in texto or b"too many" in texto or b"more than" in texto


def deduplicar(features: list) -> tuple[list, int]:
    """La fuente incluye ambos extremos: el evento compartido se queda una sola vez."""
    vistos: set[tuple] = set()
    unicos = []
    repetidos = 0
    for feature in features:
        clave = (feature.get("id"), (feature.get("properties") or {}).get("updated"))
        if clave in vistos:
            repetidos += 1
            continue
        vistos.add(clave)
        unicos.append(feature)
    return unicos, repetidos


def cubrir(inicio: datetime, fin: datetime, pedir, profundidad: int = 0) -> tuple[list, list]:
    """Devuelve `(features, consultas)`. Un exceso parte el intervalo; no recorta la lista."""
    url = url_consulta(inicio, fin)
    status, cuerpo = pedir(url)
    consulta = {
        "url": url,
        "http_status": status,
        "bytes": len(cuerpo),
        "inicio": inicio.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fin": fin.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if es_exceso(status, cuerpo) or (status == 200 and _cuenta(cuerpo) >= LIMITE_USGS):
        if profundidad > 24:
            raise RuntimeError(f"no se pudo partir la consulta {url}")
        izquierda, derecha = partir(inicio, fin)
        f1, c1 = cubrir(*izquierda, pedir, profundidad + 1)
        f2, c2 = cubrir(*derecha, pedir, profundidad + 1)
        return f1 + f2, [consulta | {"features": "partido"}] + c1 + c2
    if status == 204:
        consulta["features"] = 0
        return [], [consulta]
    if status != 200:
        raise RuntimeError(f"http_{status} url={url}")
    features = json.loads(cuerpo)["features"]
    consulta["features"] = len(features)
    return features, [consulta]


def _cuenta(cuerpo: bytes) -> int:
    try:
        features = json.loads(cuerpo).get("features")
    except (json.JSONDecodeError, AttributeError):
        return 0
    return len(features) if isinstance(features, list) else 0


def guardar(directorio: Path, anio: int, features: list, consultas: list, repetidos: int) -> Path:
    destino = directorio / str(anio)
    destino.mkdir(parents=True, exist_ok=True)
    eventos = destino / "eventos.geojson"
    eventos.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    manifiesto = {
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filtros": {"anio": anio, "minmagnitude": 4, "eventtype": "earthquake", "ambito": "mundial"},
        "eventos": len(features),
        "duplicados_de_extremo": repetidos,
        "consultas": consultas,
    }
    (destino / "manifest.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return eventos


def _bajar(url: str, timeout: float) -> tuple[int, bytes]:
    peticion = Request(url, headers={"User-Agent": "seismic-observatory/1.0", "Accept": "application/json"})
    try:
        with urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.status, respuesta.read()
    except HTTPError as exc:
        if es_transitorio(exc.code):
            raise ErrorTransitorio(f"http_{exc.code}") from exc
        return exc.code, exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise ErrorTransitorio("red") from exc


def _pedir(url: str):
    espera = 1
    ultimo = None
    for _ in range(6):
        try:
            status, cuerpo = _bajar(url, 60)
        except ErrorTransitorio as exc:
            ultimo = exc
            time.sleep(espera)
            espera = min(espera * 2, 30)
            continue
        if status == 429 or status >= 500:
            time.sleep(espera)
            espera = min(espera * 2, 30)
            continue
        return status, cuerpo
    raise ErrorTransitorio(getattr(ultimo, "motivo", "red"))


def main() -> int:
    import os

    anio = int(os.environ.get("HISTORICO_ANIO", ANIO_DEFECTO))
    directorio = Path(os.environ.get("HISTORICO_DIR", "/data/historico"))
    features: list = []
    consultas: list = []
    for inicio, fin in meses(anio):
        trozo, hechas = cubrir(inicio, fin, _pedir)
        features.extend(trozo)
        consultas.extend(hechas)
        print(f"intervalo={inicio.date()} features={len(trozo)}", flush=True)
    unicos, repetidos = deduplicar(features)
    ruta = guardar(directorio, anio, unicos, consultas, repetidos)
    print(f"eventos={len(unicos)} duplicados_de_extremo={repetidos} archivo={ruta}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
