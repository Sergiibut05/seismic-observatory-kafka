"""Configuración por variables de entorno (contracts/variables-entorno.md).

Cada servicio declara qué variables lee. Los mensajes de error nombran la variable y
nunca incluyen valores; la contraseña no aparece en `repr()` ni `str()`.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from observatorio.common.retry import Backoff

_NIVELES_LOG = ("DEBUG", "INFO", "WARNING", "ERROR")


class ConfigError(Exception):
    """Configuración ausente o inválida. El mensaje nombra la variable, nunca su valor."""


def _texto(env: Mapping[str, str], nombre: str, defecto: str) -> str:
    # Una variable vacía equivale a ausente: Compose pasa `${VAR:-valor}` y puede quedar vacía.
    return env.get(nombre) or defecto


def _obligatoria(env: Mapping[str, str], nombre: str) -> str:
    valor = env.get(nombre)
    if not valor:
        raise ConfigError(f"falta la variable de entorno obligatoria {nombre}")
    return valor


def _entero(env: Mapping[str, str], nombre: str, defecto: int, minimo: int = 1, maximo: int | None = None) -> int:
    bruto = env.get(nombre) or str(defecto)
    try:
        valor = int(bruto)
    except ValueError:
        raise ConfigError(f"valor inválido en la variable {nombre}: debe ser un entero") from None
    if valor < minimo or (maximo is not None and valor > maximo):
        limite = f">= {minimo}" if maximo is None else f"entre {minimo} y {maximo}"
        raise ConfigError(f"valor inválido en la variable {nombre}: debe ser un entero {limite}")
    return valor


def _numero_positivo(env: Mapping[str, str], nombre: str, defecto: float) -> float:
    bruto = env.get(nombre) or str(defecto)
    try:
        valor = float(bruto)
    except ValueError:
        raise ConfigError(f"valor inválido en la variable {nombre}: debe ser un número") from None
    if not valor > 0 or valor == float("inf"):
        raise ConfigError(f"valor inválido en la variable {nombre}: debe ser un número > 0")
    return int(valor) if valor == int(valor) else valor


@dataclass(frozen=True)
class AjustesPostgres:
    host: str
    port: int
    user: str
    db: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class AjustesComunes:
    log_level: str
    retry_initial_seconds: float
    retry_factor: float
    retry_max_seconds: float
    health_probe_interval_seconds: int
    health_port: int

    @property
    def backoff(self) -> Backoff:
        return Backoff(self.retry_initial_seconds, self.retry_factor, self.retry_max_seconds)


@dataclass(frozen=True)
class AjustesProductor(AjustesComunes):
    kafka_bootstrap_servers: str
    topic_live: str
    topic_partitions: int
    topic_retention_ms: int
    smoke_timeout_seconds: int
    probe_fallos_reinicio: int

    def secretos(self) -> tuple[str, ...]:
        return ()


@dataclass(frozen=True)
class AjustesConsumidor(AjustesComunes):
    kafka_bootstrap_servers: str
    topic_live: str
    consumer_group: str
    catalogo_path: str
    probe_fallos_reinicio: int
    postgres: AjustesPostgres

    def secretos(self) -> tuple[str, ...]:
        return (self.postgres.password,)


@dataclass(frozen=True)
class AjustesApi(AjustesComunes):
    postgres: AjustesPostgres

    def secretos(self) -> tuple[str, ...]:
        return (self.postgres.password,)


def _comunes(env: Mapping[str, str]) -> dict:
    nivel = _texto(env, "LOG_LEVEL", "INFO").upper()
    if nivel not in _NIVELES_LOG:
        raise ConfigError("valor inválido en la variable LOG_LEVEL: debe ser DEBUG, INFO, WARNING o ERROR")
    inicial = _numero_positivo(env, "RETRY_INITIAL_SECONDS", 1)
    factor = _numero_positivo(env, "RETRY_FACTOR", 2)
    tope = _numero_positivo(env, "RETRY_MAX_SECONDS", 30)
    if tope < inicial:
        raise ConfigError("valor inválido en la variable RETRY_MAX_SECONDS: no puede ser menor que RETRY_INITIAL_SECONDS")
    return {
        "log_level": nivel,
        "retry_initial_seconds": inicial,
        "retry_factor": factor,
        "retry_max_seconds": tope,
        "health_probe_interval_seconds": _entero(env, "HEALTH_PROBE_INTERVAL_SECONDS", 5),
        "health_port": _entero(env, "HEALTH_PORT", 8081, 1, 65535),
    }


def _postgres(env: Mapping[str, str]) -> AjustesPostgres:
    return AjustesPostgres(
        host=_texto(env, "POSTGRES_HOST", "postgres"),
        port=_entero(env, "POSTGRES_PORT", 5432, 1, 65535),
        user=_texto(env, "POSTGRES_USER", "observatorio"),
        db=_texto(env, "POSTGRES_DB", "observatorio"),
        password=_obligatoria(env, "POSTGRES_PASSWORD"),
    )


def ajustes_productor(env: Mapping[str, str] | None = None) -> AjustesProductor:
    env = os.environ if env is None else env
    return AjustesProductor(
        **_comunes(env),
        kafka_bootstrap_servers=_texto(env, "KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"),
        topic_live=_texto(env, "TOPIC_LIVE", "eventos.live"),
        topic_partitions=_entero(env, "TOPIC_PARTITIONS", 3),
        topic_retention_ms=_entero(env, "TOPIC_RETENTION_MS", 604_800_000),
        smoke_timeout_seconds=_entero(env, "SMOKE_TIMEOUT_SECONDS", 30),
        probe_fallos_reinicio=_entero(env, "PROBE_FALLOS_REINICIO", 3),
    )


def ajustes_consumidor(env: Mapping[str, str] | None = None) -> AjustesConsumidor:
    env = os.environ if env is None else env
    return AjustesConsumidor(
        **_comunes(env),
        kafka_bootstrap_servers=_texto(env, "KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"),
        topic_live=_texto(env, "TOPIC_LIVE", "eventos.live"),
        consumer_group=_texto(env, "CONSUMER_GROUP", "consumidor-live"),
        catalogo_path=_texto(env, "CATALOGO_PATH", "/catalogo/paises.geojson"),
        probe_fallos_reinicio=_entero(env, "PROBE_FALLOS_REINICIO", 3),
        postgres=_postgres(env),
    )


def ajustes_api(env: Mapping[str, str] | None = None) -> AjustesApi:
    env = os.environ if env is None else env
    return AjustesApi(**_comunes(env), postgres=_postgres(env))
