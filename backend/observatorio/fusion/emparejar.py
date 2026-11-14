"""Emparejar informes de fuentes distintas y construir el evento fusionado (Python puro).

Regla (medida en specs/013-multifuente/research.md):
- Dos informes son el mismo terremoto si son de fuentes distintas, sus horas de ocurrencia
  difieren como mucho `VENTANA_MS` y sus epicentros como mucho `DISTANCIA_KM`.
- Dos informes de la misma fuente nunca se fusionan (las réplicas de un terremoto caen dentro
  de la ventana); un evento tiene como mucho un informe por fuente.
- Si hay varios candidatos, gana el de menor `Δt/ventana + d/distancia`; a igualdad, el id menor.
- Una vez dentro de un evento, un informe no cambia de evento (sus revisiones tampoco).

Determinista: el mismo estado y los mismos informes producen los mismos mensajes, byte a byte.
Así, si la fusión escribe en Kafka y cae antes de guardar su estado, la reentrega es idéntica y
el consumidor la descarta.
"""

import bisect
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from observatorio.common.contrato import construir_mensaje_v2
from observatorio.fusion.normalizar import Informe

VENTANA_MS = 30_000
DISTANCIA_KM = 100.0
# Caja de Europa y el Mediterráneo: dentro manda EMSC; fuera, USGS.
CAJA_EUROPA = (34.0, 72.0, -25.0, 45.0)  # lat mín, lat máx, lon mín, lon máx
PREFERENCIA_EUROPA = ("emsc", "usgs")
PREFERENCIA_RESTO = ("usgs", "emsc")
_RADIO_TIERRA_KM = 6371.0


@dataclass(frozen=True)
class Canonico:
    """Lo último que se emitió de un evento fusionado."""

    id: str
    updated_ms: int
    firma: str
    fuente_principal: str


@dataclass(frozen=True)
class Resultado:
    # Informes nuevos o revisados, con el evento al que pertenecen (para guardar).
    informes: tuple[tuple[Informe, str], ...]
    # Eventos fusionados que han cambiado (para guardar).
    canonicos: tuple[Canonico, ...]
    # Mensajes v2 para `eventos.live`: (clave, valor).
    mensajes: tuple[tuple[bytes, bytes], ...]
    resumen: dict = field(default_factory=dict)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de gran círculo (haversine)."""
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * _RADIO_TIERRA_KM * math.asin(min(1.0, math.sqrt(h)))


def en_europa(latitud: float, longitud: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = CAJA_EUROPA
    return lat_min <= latitud <= lat_max and lon_min <= longitud <= lon_max


def id_canonico(informe: Informe) -> str:
    """El id de quien crea el evento. USGS tal cual (los eventos previos ya lo usan); el resto, con prefijo."""
    return informe.id_origen if informe.fuente == "usgs" else f"{informe.fuente}-{informe.id_origen}"


def puntuacion(a: Informe, b: Informe) -> float | None:
    """`None` si no pueden ser el mismo terremoto; si pueden, cuanto menor, más parecidos."""
    if a.fuente == b.fuente:
        return None
    dt = abs(a.tiempo_ms - b.tiempo_ms)
    if dt > VENTANA_MS:
        return None
    d = distancia_km(a.latitud, a.longitud, b.latitud, b.longitud)
    if d > DISTANCIA_KM:
        return None
    return dt / VENTANA_MS + d / DISTANCIA_KM


def principal(miembros: Mapping[str, Informe]) -> Informe:
    """EMSC en Europa, USGS fuera. Europa si algún informe del evento cae en la caja."""
    europa = any(en_europa(m.latitud, m.longitud) for m in miembros.values())
    for fuente in PREFERENCIA_EUROPA if europa else PREFERENCIA_RESTO:
        if fuente in miembros:
            return miembros[fuente]
    return miembros[min(miembros)]


def firma(miembros: Mapping[str, Informe]) -> str:
    return ";".join(f"{f}:{miembros[f].id_origen}:{miembros[f].updated_ms}" for f in sorted(miembros))


class _Indice:
    """Informes ordenados por hora, para buscar candidatos en la ventana con `bisect`."""

    def __init__(self):
        self._claves: list[tuple[int, str, str]] = []
        self._informes: dict[tuple[str, str], Informe] = {}

    def poner(self, informe: Informe) -> None:
        clave = (informe.fuente, informe.id_origen)
        anterior = self._informes.get(clave)
        if anterior is not None:
            self._claves.remove((anterior.tiempo_ms, anterior.fuente, anterior.id_origen))
        bisect.insort(self._claves, (informe.tiempo_ms, informe.fuente, informe.id_origen))
        self._informes[clave] = informe

    def cerca(self, tiempo_ms: int) -> Iterable[Informe]:
        desde = bisect.bisect_left(self._claves, (tiempo_ms - VENTANA_MS, "", ""))
        for t, fuente, id_origen in self._claves[desde:]:
            if t > tiempo_ms + VENTANA_MS:
                break
            yield self._informes[(fuente, id_origen)]


def fusionar(
    nuevos: Sequence[Informe],
    guardados: Iterable[tuple[Informe, str]],
    canonicos: Mapping[str, Canonico],
) -> Resultado:
    """Incorpora `nuevos` al estado (`guardados`, `canonicos`) y devuelve qué guardar y qué emitir.

    `guardados` debe traer los informes de la ventana de tiempo de `nuevos` y todos los miembros de
    los eventos a los que pertenecen (lo hace `estado.cargar`).
    """
    miembros: dict[str, dict[str, Informe]] = {}
    evento_de: dict[tuple[str, str], str] = {}
    indice = _Indice()
    for informe, canonico in guardados:
        miembros.setdefault(canonico, {})[informe.fuente] = informe
        evento_de[(informe.fuente, informe.id_origen)] = canonico
        indice.poner(informe)

    cambiados: set[str] = set()
    guardar: dict[tuple[str, str], tuple[Informe, str]] = {}
    resumen = {"informes": len(nuevos), "nuevos": 0, "revisados": 0, "sin_cambios": 0, "fusionados": 0}

    # Orden fijo: el resultado no depende del orden en que llegaron. USGS primero: si las dos fuentes
    # llegan en el mismo lote, el evento conserva el id USGS (el que ya usan la base y el replay).
    for informe in sorted(nuevos, key=_orden):
        clave = (informe.fuente, informe.id_origen)
        canonico = evento_de.get(clave)
        if canonico is not None:
            anterior = miembros[canonico][informe.fuente]
            if informe.updated_ms <= anterior.updated_ms:
                resumen["sin_cambios"] += 1  # reentrega o versión más vieja: no se toca
                continue
            resumen["revisados"] += 1
        else:
            canonico = _mejor_candidato(informe, indice, evento_de, miembros)
            if canonico is None:
                canonico = id_canonico(informe)
                if canonico in miembros or canonico in canonicos:
                    canonico = f"{informe.fuente}-{informe.id_origen}"  # colisión improbable: id con prefijo
            else:
                resumen["fusionados"] += 1
            resumen["nuevos"] += 1
            evento_de[clave] = canonico
        miembros.setdefault(canonico, {})[informe.fuente] = informe
        indice.poner(informe)
        guardar[clave] = (informe, canonico)
        cambiados.add(canonico)

    nuevos_canonicos: list[Canonico] = []
    mensajes: list[tuple[bytes, bytes]] = []
    for canonico in sorted(cambiados):
        grupo = miembros[canonico]
        previo = canonicos.get(canonico)
        sello = firma(grupo)
        if previo is not None and previo.firma == sello:
            continue
        cabeza = principal(grupo)
        version = max(max(m.updated_ms for m in grupo.values()), previo.updated_ms + 1 if previo else 0)
        nuevos_canonicos.append(Canonico(canonico, version, sello, cabeza.fuente))
        mensajes.append(mensaje_fusionado(canonico, grupo, cabeza, version))

    resumen["emitidos"] = len(mensajes)
    return Resultado(tuple(guardar.values()), tuple(nuevos_canonicos), tuple(mensajes), resumen)


def _orden(informe: Informe) -> tuple:
    return (informe.fuente != "usgs", informe.tiempo_ms, informe.fuente, informe.id_origen, informe.updated_ms)


def _mejor_candidato(
    informe: Informe,
    indice: _Indice,
    evento_de: Mapping[tuple[str, str], str],
    miembros: Mapping[str, Mapping[str, Informe]],
) -> str | None:
    mejor: tuple[float, str] | None = None
    for otro in indice.cerca(informe.tiempo_ms):
        valor = puntuacion(informe, otro)
        if valor is None:
            continue
        canonico = evento_de[(otro.fuente, otro.id_origen)]
        if informe.fuente in miembros[canonico]:
            continue  # ese evento ya tiene un informe de esta fuente
        if mejor is None or (valor, canonico) < mejor:
            mejor = (valor, canonico)
    return mejor[1] if mejor else None


def mensaje_fusionado(canonico: str, grupo: Mapping[str, Informe], cabeza: Informe, version: int) -> tuple[bytes, bytes]:
    """Mensaje v2: el evento con la forma de USGS (la que valida el consumidor) y sus fuentes."""
    coordenadas = [cabeza.longitud, cabeza.latitud, cabeza.profundidad]
    evento = {
        "type": "Feature",
        "id": canonico,
        "geometry": {"type": "Point", "coordinates": coordenadas},
        "properties": {
            "time": cabeza.tiempo_ms,
            "updated": version,
            "mag": cabeza.magnitud,
            "magType": cabeza.tipo_magnitud,
            "place": cabeza.lugar,
            "type": "earthquake",
        },
    }
    fuentes = [
        {
            "fuente": m.fuente,
            "id": m.id_origen,
            "updated": m.updated_ms,
            "principal": m.fuente == cabeza.fuente,
            "original": m.original,
        }
        for m in grupo.values()
    ]
    ingesta = max(m.ingested_at for m in grupo.values())
    return construir_mensaje_v2(evento, fuentes, cabeza.fuente, ingesta)
