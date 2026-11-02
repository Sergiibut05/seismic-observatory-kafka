# Contrato: variables de entorno

**Requisitos**: FR-026, FR-008, FR-005. **Ficheros**: `.env.example` (plantilla sin credenciales, versionada), `.env` (real, **ignorado por Git**), `compose.yaml` (mapea cada variable al servicio que la necesita; no usa `env_file`).
**Implementación**: `backend/observatorio/common/config.py` (cada servicio declara qué variables lee; si falta una obligatoria falla con `ConfigError: falta la variable de entorno obligatoria NOMBRE` y código de salida 2; el mensaje nunca incluye valores).

Columna **Origen**: `.env` = el alumno puede cambiarla; `compose` = valor fijo en `compose.yaml` (aparece en `.env.example` solo como comentario).

| Variable | Servicios | Defecto | Oblig. | Origen | Descripción |
| --- | --- | --- | --- | --- | --- |
| `POSTGRES_PASSWORD` | postgres, producer, consumer, api | — | **sí** | `.env` | Contraseña de la base. `${POSTGRES_PASSWORD:?…}`: sin ella (o vacía) Compose falla nombrándola. **Sin valor por defecto** |
| `POSTGRES_USER` | postgres, producer, consumer, api | `observatorio` | no | `.env` | Usuario de la base |
| `POSTGRES_DB` | postgres, producer, consumer, api | `observatorio` | no | `.env` | Nombre de la base |
| `POSTGRES_HOST` | producer, consumer, api | `postgres` | no | compose | Nombre del servicio (FR-006) |
| `POSTGRES_PORT` | producer, consumer, api | `5432` | no | compose | Puerto interno (no se publica) |
| `KAFKA_BOOTSTRAP_SERVERS` | producer, consumer | `kafka:19092` | no | compose | Listener **interno** (FR-006, FR-025) |
| `TOPIC_LIVE` | producer, consumer | `eventos.live` | no | `.env` | Nombre del topic live |
| `TOPIC_REPLAY` | producer, consumer | `eventos.replay` | no | `.env` | Topic de la reproducción histórica (feature 004). Mismo grupo que el live |
| `TOPIC_PARTITIONS` | producer | `3` | no | `.env` | Particiones al crear el topic |
| `TOPIC_RETENTION_MS` | producer | `604800000` (7 días) | no | `.env` | `retention.ms` del topic; entero > 0 (finito). `segment.ms` = `min(TOPIC_RETENTION_MS, 86400000)` |
| `CONSUMER_GROUP` | consumer | `consumidor-live` | no | `.env` | `group_id` de Kafka |
| `CATALOGO_PATH` | consumer, producer (solo `historico_cargar`) | `/catalogo/paises.geojson` | no | compose | Ruta (en el contenedor) del catálogo, montado en solo lectura. El productor lo monta desde la feature 005 para asignar país al cargar 2025 |
| `HISTORICO_DIR` | producer (comandos sueltos) | `/data/historico` | no | comando | Carpeta del histórico (`<HISTORICO_DIR>/2025/eventos.geojson`); la lee `python -m observatorio.historico_cargar` (feature 005) |
| `HISTORICO_CONEXION_SEGUNDOS` | producer (`historico_cargar`) | `30` | no | `.env` | Segundos máximos esperando a PostgreSQL; si se agotan, el cargador sale con código 1 |
| `RETRY_INITIAL_SECONDS` | producer, consumer, api | `1` | no | `.env` | Primera espera del backoff |
| `RETRY_FACTOR` | producer, consumer, api | `2` | no | `.env` | Factor multiplicador |
| `RETRY_MAX_SECONDS` | producer, consumer, api | `30` | no | `.env` | Tope de espera |
| `HEALTH_PROBE_INTERVAL_SECONDS` | producer, consumer, api | `5` | no | `.env` | Periodo de las sondas de dependencias |
| `PROBE_FALLOS_REINICIO` | producer, consumer, api | `3` | no | `.env` | Fallos consecutivos de la sonda (Kafka en productor y consumidor; PostgreSQL en consumidor y API) tras los que se recrea la sesión |
| `HEALTH_PORT` | producer, consumer, api (solo su healthcheck) | `8081` | no | compose | Puerto del `/health` que consulta `common/healthcheck.py` (siempre `http://127.0.0.1:<HEALTH_PORT>/health`, dentro del propio contenedor). En productor y consumidor es además el puerto del servidor de salud interno (no se publica); en la API `compose.yaml` lo fija a `8000` solo para el healthcheck, porque la API sirve su `/health` en 8000. **No existe `HEALTH_URL`**: la URL es una constante derivada, no configurable |
| `SMOKE_TIMEOUT_SECONDS` | producer (humo) | `30` | no | `.env` | Tiempo máximo para obtener el acuse de Kafka en la prueba de humo |
| `USGS_FEED_URL` | producer | feed `all_day.geojson` | no | `.env` | Feed USGS de las últimas 24 h (feature 002) |
| `POLL_INTERVAL_SECONDS` | producer | `60` | no | `.env` | Segundos entre consultas al feed |
| `HTTP_TIMEOUT_SECONDS` | producer | `30` | no | `.env` | Timeout de cada GET |
| `FEED_DIR` | producer | `/data/usgs` | no | compose | Carpeta del GeoJSON original (montada desde `data/usgs`) |
| `FEED_RETENTION_HOURS` | producer | `48` | no | `.env` | Horas que se conservan las copias del original |
| `LOG_LEVEL` | producer, consumer, api | `INFO` | no | `.env` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGEN_NETLIFY` | api | — (vacía) | no | `.env` | Origen exacto del panel en Netlify (feature 005): `https://host[:puerto]`, sin ruta, sin `/` final y sin `*`; si no, `ConfigError` (código 2, sin mostrar el valor). Vacía = solo `http://localhost:4200` y un aviso en el log. Sin credenciales CORS |
| `DATOS_DESACTUALIZADOS_SEGUNDOS` | api | `300` | no | `.env` | Segundos sin consulta correcta a USGS (HTTP 200 y sin error) a partir de los cuales `/status` da `datos_desactualizados=true`; entero ≥ 60 (el productor consulta cada 60 s) |

Reglas:

- Enteros y números se validan al arrancar (`RETRY_*` > 0, `RETRY_MAX_SECONDS ≥ RETRY_INITIAL_SECONDS`, `TOPIC_RETENTION_MS > 0`, `TOPIC_PARTITIONS ≥ 1`); un valor inválido falla nombrando la variable.
- El productor lee `POSTGRES_*` desde la 002 para recordar las versiones ya publicadas. La contraseña se redacta en los logs.
- `CLUSTER_ID` de Kafka es una constante de `compose.yaml` (no es secreto; debe ser fijo, R-03).
- `.env.example` enumera **todas** las variables anteriores con su valor por defecto, `POSTGRES_PASSWORD=` vacío y comentarios en español; las de origen `compose` van comentadas.
