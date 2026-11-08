"""Casos controlados (feature 007, FR-012): `python -m observatorio.producer.casos [--listar] [--solo NOMBRE …] [--base ISO]`.

Publica en el topic live unos eventos sintéticos que ejercitan cada regla del observatorio: nuevo,
reenvío, revisión, versión antigua, magnitud nula, coordenadas inválidas, mar y profundidad negativa.
Todos llevan `source=synthetic-casos` e `id` con el prefijo `synthetic-caso-`.

`--base` (por defecto, la hora UTC en curso truncada) fija `time` y `updated`: repetir el comando
en la misma hora reenvía exactamente las mismas versiones, así que el recuento no cambia (idempotencia).
`result=publicado` solo se escribe tras el acuse de Kafka (`acks=all`).

`construir_casos` y `seleccionar` son puros; `publicar` es lo único que toca Kafka.
"""

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from observatorio.common.config import AjustesProductor, ajustes_productor, cargar_o_salir
from observatorio.common.contrato import construir_mensaje
from observatorio.common.kafka import cerrar_sin_error
from observatorio.common.logging import configurar_logging, registrar
from observatorio.common.retry import motivo_de, reintentar
from observatorio.common.tiempo import EPOCH
from observatorio.producer.smoke import _preparar

SOURCE = "synthetic-casos"
PREFIJO_ID = "synthetic-caso-"
_MS = timedelta(milliseconds=1)
_REVISION_MS = 60_000

NOMBRES = (
    "nuevo",
    "reenvio",
    "revision",
    "antigua",
    "magnitud_nula",
    "coordenadas_invalidas",
    "mar",
    "profundidad_negativa",
)

# Qué debe verse tras publicar cada caso (lo comprueba el verifier con SQL).
ESPERADO = {
    "nuevo": "una fila actual y una versión (España)",
    "reenvio": "mismo recuento; el consumidor registra result=omitido",
    "revision": "actual = v2 (Francia, M 4.5); España −1 y Francia +1; dos versiones",
    "antigua": "el estado actual no cambia; la versión queda en el historial (tres versiones)",
    "magnitud_nula": "magnitud NULL (ND en el panel); cuenta en sin_valor",
    "coordenadas_invalidas": "ingesta.cuarentena (coordenadas_fuera_de_rango); nada en live.*",
    "mar": "pais_codigo NULL, «Sin país asignado», cuenta en los recuentos",
    "profundidad_negativa": "se conserva −2 km (intervalo «< 0»)",
}

_log = logging.getLogger("observatorio.casos")


@dataclass(frozen=True)
class Caso:
    nombre: str
    paso: str
    clave: bytes
    valor: bytes


def base_por_defecto(ahora: datetime | None = None) -> datetime:
    """Hora UTC en curso, truncada: dentro de la misma hora, el mismo `time` y `updated`."""
    ahora = ahora or datetime.now(timezone.utc)
    return ahora.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _ms(instante: datetime) -> int:
    return (instante.astimezone(timezone.utc) - EPOCH) // _MS


def _evento(sufijo: str, descripcion: str, tiempo_ms: int, updated_ms: int, mag, coordenadas: list) -> dict:
    """Feature GeoJSON con la forma de USGS. `mag=None` se conserva como `null`."""
    return {
        "type": "Feature",
        "id": PREFIJO_ID + sufijo,
        "properties": {
            "mag": mag,
            "place": f"SINTÉTICO · caso {descripcion} (no es un terremoto real)",
            "time": tiempo_ms,
            "updated": updated_ms,
            "type": "earthquake",
            "title": f"SINTÉTICO · caso {descripcion}",
        },
        "geometry": {"type": "Point", "coordinates": coordenadas},
    }


def construir_casos(base: datetime, ingestado: datetime | None = None) -> list[Caso]:
    """Los mensajes de los ocho casos, en el orden en que deben publicarse.

    `base` fija `time` y `updated` (mismo `base`, mismos bytes del evento). `ingestado` solo afecta a
    `ingested_at`; el reenvío lleva `ingestado + 1 s` para ser «el mismo mensaje con otra ingesta».
    """
    if base.tzinfo is None or base.utcoffset() is None:
        raise ValueError("base sin zona horaria")
    ingestado = ingestado or datetime.now(timezone.utc)
    t = _ms(base)
    nueva_ingesta = ingestado + timedelta(seconds=1)

    def caso(nombre: str, paso: str, evento: dict, ingesta: datetime = ingestado) -> Caso:
        clave, valor = construir_mensaje(evento, SOURCE, "live", ingesta)
        return Caso(nombre, paso, clave, valor)

    nuevo = _evento("nuevo", "nuevo", t, t, 3.4, [-3.7, 40.4, 10])
    version_1 = _evento("revision", "revisión v1", t, t, 2.0, [-3.7, 40.4, 10])
    version_2 = _evento("revision", "revisión v2", t, t + _REVISION_MS, 4.5, [2.3, 48.9, 8])
    antigua = _evento("revision", "versión antigua", t, t - _REVISION_MS, 9.0, [2.3, 48.9, 8])
    return [
        caso("nuevo", "unico", nuevo),
        caso("reenvio", "unico", nuevo, nueva_ingesta),
        caso("revision", "v1", version_1),
        caso("revision", "v2", version_2),
        # Tras la v2: su `updated` es anterior y no puede reemplazar el estado actual.
        caso("antigua", "unico", antigua),
        caso("magnitud_nula", "unico", _evento("magnitud-nula", "magnitud nula", t, t, None, [-3.7, 40.4, 10])),
        caso(
            "coordenadas_invalidas", "unico",
            _evento("coordenadas-invalidas", "coordenadas inválidas", t, t, 3.0, [200, 10, 5]),
        ),
        caso("mar", "unico", _evento("mar", "en el mar", t, t, 3.0, [-30, 0, 10])),
        caso(
            "profundidad_negativa", "unico",
            _evento("profundidad-negativa", "profundidad negativa", t, t, 3.0, [-3.7, 40.4, -2]),
        ),
    ]


def seleccionar(casos: Sequence[Caso], nombres: Sequence[str] | None) -> list[Caso]:
    """Filtra por nombre de caso conservando el orden de publicación; un nombre desconocido es `ValueError`."""
    if not nombres:
        return list(casos)
    desconocidos = [n for n in nombres if n not in NOMBRES]
    if desconocidos:
        raise ValueError(f"caso desconocido: {', '.join(desconocidos)} (válidos: {', '.join(NOMBRES)})")
    pedidos = set(nombres)
    return [caso for caso in casos if caso.nombre in pedidos]


def _instante_base(texto: str) -> datetime:
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError("se esperaba un instante ISO 8601 con zona, p. ej. 2026-11-08T14:00:00Z") from None
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise argparse.ArgumentTypeError("la base necesita zona horaria (Z u offset)")
    return instante.astimezone(timezone.utc)


def leer_argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m observatorio.producer.casos", description=__doc__.split("\n\n")[0])
    analizador.add_argument("--listar", action="store_true", help="muestra los casos y su resultado esperado, sin publicar")
    analizador.add_argument("--solo", nargs="+", metavar="NOMBRE", help=f"solo estos casos ({', '.join(NOMBRES)})")
    analizador.add_argument("--base", type=_instante_base, metavar="ISO", help="instante de `time` y `updated` (defecto: la hora UTC en curso)")
    return analizador.parse_args(argv)


async def _publicar(ajustes: AjustesProductor, casos: Sequence[Caso]) -> None:
    productor = await reintentar(lambda: _preparar(ajustes), dependency="kafka", config=ajustes.backoff, logger=_log)
    try:
        for caso in casos:
            metadatos = await productor.send_and_wait(ajustes.topic_live, value=caso.valor, key=caso.clave)
            # Después del acuse: `send_and_wait` devuelve cuando Kafka lo confirmó (acks=all).
            registrar(
                _log,
                "publicado",
                caso=caso.nombre,
                paso=caso.paso,
                event_id=caso.clave.decode("utf-8"),
                updated=_actualizado(caso),
                topic=metadatos.topic,
                partition=metadatos.partition,
                offset=metadatos.offset,
            )
    finally:
        await cerrar_sin_error(productor)


def _actualizado(caso: Caso) -> int:
    return json.loads(caso.valor)["event"]["properties"]["updated"]


async def publicar(ajustes: AjustesProductor, casos: Sequence[Caso]) -> int:
    try:
        await asyncio.wait_for(_publicar(ajustes, casos), ajustes.smoke_timeout_seconds)
    except asyncio.TimeoutError:
        registrar(_log, "error", nivel="ERROR", reason="sin_acuse", timeout_s=ajustes.smoke_timeout_seconds)
        return 1
    except Exception as exc:
        registrar(_log, "error", nivel="ERROR", reason=motivo_de(exc))
        return 1
    return 0


def _listar(casos: Sequence[Caso]) -> None:
    for caso in casos:
        print(
            f"{caso.nombre:<22} {caso.paso:<6} {caso.clave.decode():<42} updated={_actualizado(caso)}  → {ESPERADO[caso.nombre]}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = leer_argumentos(argv)
    base = args.base or base_por_defecto()
    try:
        casos = seleccionar(construir_casos(base), args.solo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.listar:
        _listar(casos)
        return 0
    ajustes = cargar_o_salir("producer", ajustes_productor)
    configurar_logging("producer", ajustes.log_level, ajustes.secretos())
    return asyncio.run(publicar(ajustes, casos))


if __name__ == "__main__":
    sys.exit(main())
