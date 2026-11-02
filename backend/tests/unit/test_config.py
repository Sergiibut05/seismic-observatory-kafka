"""Pruebas de la configuración por entorno (contracts/variables-entorno.md)."""

import pytest

from observatorio.common.config import (
    ConfigError,
    ajustes_api,
    ajustes_consumidor,
    ajustes_productor,
)

CONTRASENA = "s3cr3to-Ú-no-debe-salir"


def entorno(**extra):
    base = {"POSTGRES_PASSWORD": CONTRASENA}
    base.update(extra)
    return base


# --- variable obligatoria -------------------------------------------------


@pytest.mark.parametrize("fabrica", [ajustes_consumidor, ajustes_api, ajustes_productor])
def test_falta_contrasena(fabrica):
    with pytest.raises(ConfigError) as exc:
        fabrica({})
    assert "POSTGRES_PASSWORD" in str(exc.value)


@pytest.mark.parametrize("fabrica", [ajustes_consumidor, ajustes_api, ajustes_productor])
def test_contrasena_vacia_equivale_a_ausente(fabrica):
    with pytest.raises(ConfigError) as exc:
        fabrica({"POSTGRES_PASSWORD": ""})
    assert "POSTGRES_PASSWORD" in str(exc.value)


def test_el_mensaje_de_error_no_contiene_valores():
    with pytest.raises(ConfigError) as exc:
        ajustes_consumidor(entorno(RETRY_INITIAL_SECONDS="0"))
    mensaje = str(exc.value)
    assert "RETRY_INITIAL_SECONDS" in mensaje
    assert CONTRASENA not in mensaje


# --- valores por defecto --------------------------------------------------


def test_defectos_del_consumidor():
    a = ajustes_consumidor(entorno())
    assert a.kafka_bootstrap_servers == "kafka:19092"
    assert a.topic_live == "eventos.live"
    assert a.consumer_group == "consumidor-live"
    assert a.catalogo_path == "/catalogo/paises.geojson"
    assert a.postgres.host == "postgres"
    assert a.postgres.port == 5432
    assert a.postgres.user == "observatorio"
    assert a.postgres.db == "observatorio"
    assert a.postgres.password == CONTRASENA
    assert a.retry_initial_seconds == 1
    assert a.retry_factor == 2
    assert a.retry_max_seconds == 30
    assert a.health_probe_interval_seconds == 5
    assert a.probe_fallos_reinicio == 3
    assert a.health_port == 8081
    assert a.log_level == "INFO"


def test_defectos_del_productor():
    a = ajustes_productor(entorno())
    assert a.kafka_bootstrap_servers == "kafka:19092"
    assert a.topic_live == "eventos.live"
    assert a.topic_partitions == 3
    assert a.topic_retention_ms == 604_800_000
    assert a.smoke_timeout_seconds == 30
    assert a.poll_interval_seconds == 60
    assert a.http_timeout_seconds == 30
    assert a.feed_dir == "/data/usgs"
    assert a.feed_retention_hours == 48
    assert a.usgs_feed_url.endswith("/all_day.geojson")
    assert a.probe_fallos_reinicio == 3
    assert a.health_port == 8081
    assert a.log_level == "INFO"


def test_defectos_de_la_api():
    a = ajustes_api(entorno())
    assert a.postgres.host == "postgres"
    assert a.health_probe_interval_seconds == 5
    assert a.log_level == "INFO"


def test_variables_personalizadas():
    a = ajustes_consumidor(
        entorno(
            TOPIC_LIVE="otro.topic",
            CONSUMER_GROUP="grupo-x",
            POSTGRES_USER="u",
            POSTGRES_DB="d",
            POSTGRES_HOST="h",
            POSTGRES_PORT="5433",
            RETRY_INITIAL_SECONDS="2",
            RETRY_FACTOR="3",
            RETRY_MAX_SECONDS="20",
            HEALTH_PORT="9000",
            LOG_LEVEL="DEBUG",
        )
    )
    assert a.topic_live == "otro.topic"
    assert a.consumer_group == "grupo-x"
    assert (a.postgres.user, a.postgres.db, a.postgres.host, a.postgres.port) == ("u", "d", "h", 5433)
    assert (a.retry_initial_seconds, a.retry_factor, a.retry_max_seconds) == (2, 3, 20)
    assert a.health_port == 9000
    assert a.log_level == "DEBUG"


def test_variable_vacia_con_defecto_usa_el_defecto():
    # Compose pasa `${VAR:-valor}`; una variable vacía no debe invalidar la configuración.
    a = ajustes_consumidor(entorno(TOPIC_LIVE="", RETRY_MAX_SECONDS=""))
    assert a.topic_live == "eventos.live"
    assert a.retry_max_seconds == 30


# --- validación de números ------------------------------------------------


@pytest.mark.parametrize(
    "variable,valor",
    [
        ("RETRY_INITIAL_SECONDS", "0"),
        ("RETRY_INITIAL_SECONDS", "-1"),
        ("RETRY_INITIAL_SECONDS", "uno"),
        ("RETRY_FACTOR", "0"),
        ("RETRY_FACTOR", "x"),
        ("RETRY_MAX_SECONDS", "0"),
        ("HEALTH_PROBE_INTERVAL_SECONDS", "0"),
        ("PROBE_FALLOS_REINICIO", "0"),
        ("HEALTH_PORT", "0"),
        ("HEALTH_PORT", "70000"),
        ("HEALTH_PORT", "abc"),
        ("POSTGRES_PORT", "no"),
        ("LOG_LEVEL", "VERBOSE"),
    ],
)
def test_valores_invalidos_nombran_la_variable(variable, valor):
    with pytest.raises(ConfigError) as exc:
        ajustes_consumidor(entorno(**{variable: valor}))
    assert variable in str(exc.value)


def test_tope_menor_que_la_espera_inicial():
    with pytest.raises(ConfigError) as exc:
        ajustes_consumidor(entorno(RETRY_INITIAL_SECONDS="10", RETRY_MAX_SECONDS="5"))
    assert "RETRY_MAX_SECONDS" in str(exc.value)


@pytest.mark.parametrize(
    "variable,valor",
    [
        ("TOPIC_RETENTION_MS", "0"),
        ("TOPIC_RETENTION_MS", "-5"),
        ("TOPIC_RETENTION_MS", "siete dias"),
        ("TOPIC_PARTITIONS", "0"),
        ("TOPIC_PARTITIONS", "tres"),
        ("SMOKE_TIMEOUT_SECONDS", "0"),
    ],
)
def test_valores_invalidos_del_productor(variable, valor):
    with pytest.raises(ConfigError) as exc:
        ajustes_productor(entorno(**{variable: valor}))
    assert variable in str(exc.value)


def test_retencion_personalizada():
    assert ajustes_productor(entorno(TOPIC_RETENTION_MS="3600000")).topic_retention_ms == 3_600_000


# --- el productor guarda el estado de lo publicado en PostgreSQL ----------


def test_el_productor_rechaza_un_puerto_de_postgres_invalido():
    with pytest.raises(ConfigError) as exc:
        ajustes_productor(entorno(POSTGRES_PORT="no-numerico"))
    assert "POSTGRES_PORT" in str(exc.value)


# --- los secretos no salen en repr/str ------------------------------------


@pytest.mark.parametrize("fabrica", [ajustes_consumidor, ajustes_api, ajustes_productor])
def test_repr_y_str_no_contienen_la_contrasena(fabrica):
    a = fabrica(entorno())
    assert CONTRASENA not in repr(a)
    assert CONTRASENA not in str(a)
    assert CONTRASENA not in repr(a.postgres)
    assert CONTRASENA not in str(a.postgres)


@pytest.mark.parametrize("fabrica", [ajustes_consumidor, ajustes_api, ajustes_productor])
def test_secretos_conocidos_para_redactar_logs(fabrica):
    assert CONTRASENA in fabrica(entorno()).secretos()


def test_backoff_derivado_de_los_ajustes():
    b = ajustes_consumidor(entorno(RETRY_INITIAL_SECONDS="2", RETRY_FACTOR="3", RETRY_MAX_SECONDS="20")).backoff
    assert (b.inicial, b.factor, b.tope) == (2, 3, 20)


def test_ajustes_inmutables():
    a = ajustes_consumidor(entorno())
    with pytest.raises(Exception):
        a.topic_live = "otro"

@pytest.mark.parametrize("fabrica", [ajustes_productor, ajustes_consumidor, ajustes_api])
def test_los_tres_servicios_leen_probe_fallos_reinicio(fabrica):
    assert fabrica(entorno()).probe_fallos_reinicio == 3
    assert fabrica(entorno(PROBE_FALLOS_REINICIO="5")).probe_fallos_reinicio == 5


# --- API: CORS y umbral de datos desactualizados (feature 005) -------------


def test_api_sin_origen_netlify_solo_admite_localhost():
    a = ajustes_api(entorno())
    assert a.cors_origen_netlify == ""
    assert a.origenes_cors == ["http://localhost:4200"]
    assert ajustes_api(entorno(CORS_ORIGEN_NETLIFY="")).origenes_cors == ["http://localhost:4200"]


def test_api_con_origen_netlify_admite_los_dos():
    a = ajustes_api(entorno(CORS_ORIGEN_NETLIFY="https://observatorio-sismico.netlify.app"))
    assert a.origenes_cors == ["http://localhost:4200", "https://observatorio-sismico.netlify.app"]


def test_origen_netlify_con_puerto_y_mayusculas():
    a = ajustes_api(entorno(CORS_ORIGEN_NETLIFY="https://Panel.Netlify.app:8443"))
    assert a.cors_origen_netlify == "https://panel.netlify.app:8443"


@pytest.mark.parametrize(
    "valor",
    [
        "*",
        "https://*.netlify.app",
        "https://panel.netlify.app/",
        "https://panel.netlify.app/ruta",
        "http://panel.netlify.app",
        "panel.netlify.app",
        "https://",
        "https://panel.netlify.app:99999",
        "https://panel.netlify.app:0",
        "https://panel.netlify.app\n",
        "https://panel netlify.app",
    ],
)
def test_origen_netlify_invalido_nombra_la_variable_y_no_el_valor(valor):
    with pytest.raises(ConfigError) as exc:
        ajustes_api(entorno(CORS_ORIGEN_NETLIFY=valor))
    mensaje = str(exc.value)
    assert "CORS_ORIGEN_NETLIFY" in mensaje
    # El texto de ayuda menciona `https://` y `*`; cualquier otro valor no debe aparecer.
    assert valor.strip() in ("*", "https://") or valor.strip() not in mensaje
    assert CONTRASENA not in mensaje


def test_umbral_de_datos_desactualizados():
    assert ajustes_api(entorno()).datos_desactualizados_segundos == 300
    assert ajustes_api(entorno(DATOS_DESACTUALIZADOS_SEGUNDOS="")).datos_desactualizados_segundos == 300
    assert ajustes_api(entorno(DATOS_DESACTUALIZADOS_SEGUNDOS="60")).datos_desactualizados_segundos == 60
    assert ajustes_api(entorno(DATOS_DESACTUALIZADOS_SEGUNDOS="900")).datos_desactualizados_segundos == 900


@pytest.mark.parametrize("valor", ["59", "0", "-1", "cinco", "1.5"])
def test_umbral_invalido(valor):
    with pytest.raises(ConfigError) as exc:
        ajustes_api(entorno(DATOS_DESACTUALIZADOS_SEGUNDOS=valor))
    assert "DATOS_DESACTUALIZADOS_SEGUNDOS" in str(exc.value)


def test_el_resto_de_servicios_ignoran_las_variables_de_la_api():
    assert ajustes_consumidor(entorno(CORS_ORIGEN_NETLIFY="*")).topic_live == "eventos.live"
