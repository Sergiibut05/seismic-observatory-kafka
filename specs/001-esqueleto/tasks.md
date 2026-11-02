---

description: "Lista de tareas de la feature 001-esqueleto"
---

# Tasks: Esqueleto de extremo a extremo (walking skeleton)

**Input**: documentos de diseño en `specs/001-esqueleto/` — [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Prerrequisitos**: `plan.md` y `spec.md` aprobados. Rama `001-esqueleto`. Docker con Compose v2. Shell: PowerShell.

**Tests**: la Constitución («Flujo de trabajo») exige pytest para la lógica de validación, versionado y geografía, y la petición del alumno fija qué se prueba. **Dentro de cada fase, las tareas de prueba van antes que la implementación y deben fallar primero.** Se ejecutan en la imagen:
`docker compose run --rm --no-deps consumer pytest -q` (antes de que exista `compose.yaml` completo: `docker run --rm observatorio-backend:local pytest -q`).

**Organización**: por historia de usuario de [spec.md](spec.md). Las pruebas de integración con la pila no son tareas de código: se ejecutan con [quickstart.md](quickstart.md) (tarea «Validar» al final de cada historia).

**Nota de ordenación (revisión tras `/speckit-analyze`)**: la carga y validación del catálogo (US5) y el endpoint `/status` (FR-023) son requisitos de **arranque** del consumidor y de la API; se implementan antes del bucle de consumo, en Foundational y en US1, y US5 conserva la validación de sus escenarios.

## Formato: `[ID] [P?] [Story] Descripción con ruta`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin dependencia de tareas incompletas)
- **[USn]**: historia de usuario de la spec (US1…US6)
- Rutas relativas a la raíz del repositorio. Español en comentarios, logs, documentación y commits. Nombres de campos/tablas según la convención de [research.md R-06](research.md#r-06--nombres-de-esquemas-y-convención-de-nombres).
- Commits: uno por tarea o grupo lógico, en español.

## Mapa de historias

| Historia | Prioridad | Título | Fase |
| --- | --- | --- | --- |
| US1 | P1 | Levantar la pila completa con un comando | 3 |
| US2 | P1 | Prueba de humo de extremo a extremo con un evento sintético | 4 |
| US3 | P2 | Arranque y operación tolerantes a dependencias lentas o caídas | 5 |
| US4 | P2 | Reiniciar la pila sin perder datos | 6 |
| US5 | P2 | Catálogo de países cargado al arrancar | 7 (código en F2 y T027) |
| US6 | P3 | Diagnosticar y operar con logs, configuración y documentación únicas | 8 |

---

## Phase 1: Setup (infraestructura compartida)

**Propósito**: esqueleto de ficheros y una imagen que construye y ejecuta pytest.

- [ ] T001 Crear la estructura de paquetes vacíos: `backend/observatorio/__init__.py`, `backend/observatorio/common/__init__.py`, `backend/observatorio/producer/__init__.py`, `backend/observatorio/consumer/__init__.py`, `backend/observatorio/api/__init__.py`, y los directorios `backend/tests/unit/` y `backend/tests/fixtures/` (con un `.gitkeep` en `fixtures/`)
- [ ] T002 [P] Crear `backend/requirements.txt` con **solo** estas versiones fijadas con `==` (R-02): `aiokafka==0.15.0`, `fastapi==0.162.0`, `uvicorn==0.54.0`, `psycopg[binary]==3.3.6`, `shapely==2.2.0`, `pytest==9.2.0`; sin `pytest-asyncio`, `httpx`, `psycopg_pool`, `jsonschema`, `structlog`
- [ ] T003 [P] Crear `backend/Dockerfile` (base `python:3.12-slim`; variables `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`, `PIP_NO_CACHE_DIR=1`; `WORKDIR /app`; copiar `requirements.txt` e instalar **antes** de copiar el código para aprovechar la caché; copiar `observatorio/` y `tests/`; usuario no root `appuser` UID 10001; `CMD` por defecto `python -m observatorio.producer`; sin `curl`) y `backend/.dockerignore` (`__pycache__`, `.pytest_cache`, `.venv`, `*.log`)
- [ ] T004 [P] Crear `backend/pytest.ini` (`testpaths = tests`, `pythonpath = .`, `addopts = -ra`)
- [ ] T005 [P] Crear `.env.example` enumerando **todas** las variables de [contracts/variables-entorno.md](contracts/variables-entorno.md) (incluida `HEALTH_PORT`) con su valor por defecto, comentarios en español, `POSTGRES_PASSWORD=` **vacío** y las de origen `compose` como comentario; verificar que `.gitignore` ya ignora `.env` y no `.env.example` (`git check-ignore .env`; `git check-ignore -v .env.example` sin salida)
- [ ] T006 Construir la imagen y comprobarla: `docker build -t observatorio-backend:local backend`; `docker run --rm observatorio-backend:local python -c "import aiokafka, fastapi, uvicorn, psycopg, shapely, pytest; print('ok')"`; `docker run --rm observatorio-backend:local pytest --collect-only -q` (0 tests, sin error). Si alguna versión fijada no resuelve, **detenerse y avisar** (cambiaría R-02)

---

## Phase 2: Foundational (bloquea todas las historias)

**Propósito**: utilidades comunes puras y probadas (configuración, logs, backoff, salud, topic, catálogo).

**⚠️ CRÍTICO**: ninguna historia empieza antes de que esta fase esté en verde.

### Pruebas (escribir primero; deben fallar)

- [ ] T007 [P] Escribir `backend/tests/unit/test_config.py`: variable obligatoria ausente → `ConfigError` cuyo mensaje contiene el **nombre** de la variable y ningún valor; `POSTGRES_PASSWORD` vacía = ausente; valores por defecto de [contracts/variables-entorno.md](contracts/variables-entorno.md); enteros inválidos (`RETRY_INITIAL_SECONDS=0`, `RETRY_MAX_SECONDS < RETRY_INITIAL_SECONDS`, `TOPIC_RETENTION_MS=0`, `TOPIC_PARTITIONS=0`, texto no numérico) → `ConfigError` con el nombre; el productor **no** exige ni lee `POSTGRES_*`; `repr()`/`str()` de los ajustes no contiene la contraseña
- [ ] T008 [P] Escribir `backend/tests/unit/test_logging.py` (contrato [contracts/logs.md](contracts/logs.md)): línea con `ts` (UTC, ms, `Z`), `level`, `service`, `result`; valores con espacios, `=`, `"`, `\` y saltos de línea se entrecomillan/escapan y **nunca** producen dos líneas; `registrar()` rechaza un `result` fuera del conjunto cerrado (`publicado`, `persistido`, `omitido`, `rechazado`, `error`, `iniciado`, `listo`, `reintento`, `detenido`, `info`); un registro de librería sin `result` recibe `result=info` (o `result=error` si nivel ≥ ERROR); el *traceback* va en `exc="…"` en una línea; el valor de una contraseña conocida se sustituye por `***`; **cada** línea cumple la expresión regular de la sección «Comprobación (SC-009)»
- [ ] T009 [P] Escribir `backend/tests/unit/test_retry.py`: `esperas(inicial=1, factor=2, tope=30)` produce 1, 2, 4, 8, 16, 30, 30, 30…; respeta configuración distinta (`inicial=2, factor=3, tope=20`); `reintentar()` (con `sleep` y reloj inyectados, vía `asyncio.run`) reintenta hasta éxito, registra **cada** intento con `attempt`, `wait_s`, `dependency` y `reason` (clase de excepción, nunca el mensaje completo), no termina el proceso ante excepciones esperadas, propaga `asyncio.CancelledError`, y reinicia la secuencia de esperas tras un éxito
- [ ] T010 [P] Escribir `backend/tests/unit/test_health.py`: todas las comprobaciones **empiezan en rojo**; sano solo si todas en verde; al poner una en rojo vuelve a no sano y `failing` la nombra; `GET /health` del servidor asyncio devuelve `200 {"status":"ok"}` / `503 {"status":"unhealthy","failing":[…]}` (servidor en puerto efímero dentro de la prueba); ruta desconocida → `404`; el CLI `healthcheck` construye la URL `http://127.0.0.1:<HEALTH_PORT>/health` (puerto por defecto 8081, sin otra variable) y devuelve código 0 con 200 y 1 con 503 o conexión rechazada
- [ ] T011 [P] Escribir `backend/tests/unit/test_kafka_topic.py` (parte de **creación**, sin broker): `configuracion_topic(retention_ms)` devuelve `{"retention.ms": str(retention_ms), "segment.ms": str(min(retention_ms, 86400000))}`; con 604800000 → `segment.ms=86400000`; con 3600000 → `segment.ms=3600000`; interpretar la respuesta de `create_topics` con `topic_errors` (código 0 = creado, 36 = ya existe, otro = error → excepción); `topic_listado(nombres, topic)`
- [ ] T012 [P] Escribir `backend/tests/unit/test_catalogo.py` (US5; FR-020, FR-021) con GeoJSON temporales (`tmp_path`): válido pequeño → `Catalogo(total=N, fuente=…)`; **un caso por motivo**: `catalogo_ausente` (ruta inexistente; el detalle incluye la ruta esperada), `catalogo_ilegible` (JSON roto, no `FeatureCollection`), `catalogo_vacio` (`features: []`), `geometria_no_poligonal` (`Point`, `LineString`), `adm0_a3_ausente` (falta, `null` o cadena vacía), `adm0_a3_repetido`; geometría inválida topológicamente → no bloquea y se cuenta (`geometrias_invalidas`); prueba de integración **condicionada** a que exista `/catalogo/paises.geojson` (se salta si no está montado) que espera `total == 242`

### Implementación

- [ ] T013 Implementar `backend/observatorio/common/config.py` (T007): dataclasses inmutables por servicio (`ajustes_productor()`, `ajustes_consumidor()`, `ajustes_api()`), `ConfigError`, lectura de `os.environ` inyectable, secretos con `repr` oculto
- [ ] T014 [P] Implementar `backend/observatorio/common/logging.py` (T008): `FormateadorClaveValor`, `configurar_logging(service, nivel, secretos)`, `registrar(logger, result, nivel="INFO", **campos)`, constante `RESULTADOS`
- [ ] T015 [P] Implementar `backend/observatorio/common/retry.py` (T009): `esperas()` (generador/función pura) y `reintentar(operacion, *, dependency, sleep, config)` con registro `result=reintento`
- [ ] T016 [P] Implementar `backend/observatorio/common/health.py` (T010): `EstadoSalud` (registro de comprobaciones inicializadas en rojo), `servidor_salud(estado, puerto)` sobre `asyncio.start_server` con `GET /health`
- [ ] T017 Implementar `backend/observatorio/common/healthcheck.py` (T010, depende de T016): `python -m observatorio.common.healthcheck` hace `GET http://127.0.0.1:<HEALTH_PORT>/health` con `urllib` (timeout 3 s). **`HEALTH_PORT` es la única variable que lee** (defecto 8081; en la API `compose.yaml` la fija a 8000 para el healthcheck); **no existe `HEALTH_URL`** (decisión F2: URL derivada, no configurable). Salida 0/1
- [ ] T018 Implementar `backend/observatorio/common/kafka.py` (T011, T015): `configuracion_topic()`, `ensure_topic()` (crea con `retention.ms` y `segment.ms`, interpreta el error 36 sin excepción — [medido] en R-05), `wait_for_topic()` (usa `AIOKafkaAdminClient.list_topics()` con backoff y `result=reintento reason=topic_no_existe`), `sonda_kafka()` (metadatos bajo `asyncio.wait_for`)
- [ ] T019 Implementar `backend/observatorio/common/catalogo.py` (T012, R-18): `cargar_catalogo(ruta)` con `json` + `shapely.geometry.shape`, `CatalogoError(motivo, detalle)` con los seis motivos, sin guardar geometrías en memoria; `ADM0_A3` único con `set`
- [ ] T020 Ejecutar `docker build -t observatorio-backend:local backend` y `docker run --rm observatorio-backend:local pytest -q`: **todo en verde** (checkpoint de la fase)

**Checkpoint**: la base está lista; se puede empezar US1.

---

## Phase 3: User Story 1 — Levantar la pila completa con un comando (P1) 🎯 MVP

**Objetivo**: `docker compose up --build -d` deja los cinco servicios `healthy`, con la base inicializada, el catálogo cargado, `/health` y `/status` operativos, solo dos puertos publicados y fallo explícito sin contraseña.

**Prueba independiente**: [quickstart.md §1](quickstart.md#1-levantar-la-pila-us1--sc-001-sc-007) (SC-001, SC-007).

### Pruebas (primero)

- [ ] T021 [P] [US1] Escribir `backend/tests/unit/test_db.py` con una fábrica de conexión falsa inyectada: conecta al primer intento si la fábrica funciona; con fallos reintenta con backoff y registra `dependency=postgres`; si `max(version)` de `ingesta.version_esquema` es menor que `ESQUEMA_VERSION_REQUERIDA` (=1) o la tabla no existe, la conexión se trata como **fallida** (`reason=esquema_desactualizado`) y se reintenta; `sonda()` que falla marca desconectado y deja la comprobación `postgres` en rojo; los parámetros se pasan **por separado** (nunca una cadena de conexión) y ningún log contiene la contraseña
- [ ] T022 [P] [US1] Escribir `backend/tests/unit/test_estado_api.py` (FR-023): `armar_estado(conteos, ultimo, db_ok, ahora)` → con base conectada `base_de_datos="conectada"`, enteros y `ultimo_evento` con `updated`/`processed_at` en ISO UTC con `Z`; con la base caída `fallida` y `eventos_reales`, `eventos_sinteticos` y `ultimo_evento` **`None`** (nunca 0); sin eventos `ultimo_evento=None` y recuentos 0; los sintéticos solo se suman en `eventos_sinteticos`; el resultado cumple exactamente las claves de `contracts/api.openapi.yaml`

### Implementación

- [ ] T023 [US1] Implementar `backend/observatorio/common/db.py` (T021, T013–T016): clase `Database` con una `AsyncConnection` de `psycopg` (`autocommit=True`; transacciones con `async with conn.transaction()`), `asyncio.Lock`, `conectar()` con backoff, guarda de versión de esquema, `sonda()` (`SELECT 1`), cierre limpio
- [ ] T024 [P] [US1] Escribir `db/init/001_esquema_base.sql` **idéntico en estructura a [data-model.md §3](data-model.md#3-modelo-físico-referencia-para-dbinit001_esquema_basesql)**: esquemas `live`, `replay`, `ingesta` (con `COMMENT ON SCHEMA`); `ingesta.version_esquema` (`version integer PRIMARY KEY CHECK (version > 0)`, `nombre text NOT NULL`, `aplicada_en timestamptz NOT NULL DEFAULT clock_timestamp()`); `live.versiones_evento` con todas las columnas `NOT NULL`, `CHECK (event_id <> '')`, `CHECK (mode = 'live')`, `PRIMARY KEY (event_id, updated)`, `CHECK` de coherencia sintética y el índice `versiones_evento_processed_at_idx (processed_at DESC)`; `ingesta.cuarentena` con `UNIQUE (topic, particion, offset_kafka)`, `clave bytea` y `original bytea` (ambas nulables); todo con `IF NOT EXISTS` y la fila `(1, 'esquema_base')` con `ON CONFLICT (version) DO NOTHING`; sin `CREATE TABLE` en `replay`
- [ ] T025 [US1] Implementar `backend/observatorio/producer/app.py` y `backend/observatorio/producer/__main__.py` (T013–T018): `iniciado` → servidor de salud (rojo) → conexión a Kafka con backoff → `ensure_topic()` → `AIOKafkaProducer(acks="all", enable_idempotence=True)` → comprobación `kafka` en verde → reposo con sonda periódica (sin USGS: lo añade la 002)
- [ ] T026 [US1] Implementar la API completa de arranque (T022, T023, T024): `backend/observatorio/api/estado.py` (`armar_estado` puro + consultas de recuentos `SELECT count(DISTINCT event_id) FILTER (WHERE NOT sintetico), count(DISTINCT event_id) FILTER (WHERE sintetico) FROM live.versiones_evento` y último evento `… ORDER BY processed_at DESC LIMIT 1`, ambas bajo `asyncio.wait_for(…, 3)`), `backend/observatorio/api/main.py` y `backend/observatorio/api/__main__.py`: `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`; `GET /health` → `200 {"status":"ok"}` / `503 {"status":"unhealthy"}` sin lista de componentes; `GET /status` **siempre 200** (ante fallo de BD marca la conexión perdida y devuelve `fallida` con `null`; con la tabla vacía, recuentos 0 y `ultimo_evento: null`); `lifespan` que lanza la conexión con backoff en segundo plano (la API **no** aborta si PostgreSQL no está); `__main__` arranca `uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None, access_log=False)` tras `configurar_logging`; registro de acceso propio en `clave=valor` (DEBUG para `/health`); sin cadenas de conexión ni detalles internos en las respuestas
- [ ] T027 [US1] Implementar `backend/observatorio/consumer/app.py` y `backend/observatorio/consumer/__main__.py` (esqueleto; T023, T018, T019): `iniciado` → salud (rojo) → **cargar y validar el catálogo antes de cualquier conexión** (éxito: `result=listo component=catalogo paises=<n> fuente=<ruta>`; fallo: `result=error component=catalogo motivo=… fuente=…`, comprobación `catalogo` en rojo, **no se crea el consumidor de Kafka ni se conecta a PostgreSQL**, el proceso sigue vivo y sin reintentar la lectura — US5) → conexión a PostgreSQL con backoff → `wait_for_topic()` → `AIOKafkaConsumer(enable_auto_commit=False, auto_offset_reset="earliest", group_id=…)` → `catalogo`, `kafka` y `postgres` en verde; el bucle de consumo **no procesa ni confirma** nada todavía (se completa en T039)
- [ ] T028 [US1] Reescribir `compose.yaml` según [plan.md «Diseño de compose.yaml»](plan.md#diseño-de-composeyaml): ancla `x-backend` (`build: ./backend`, `image: observatorio-backend:local`, `restart: unless-stopped`); servicios `kafka` (se conserva lo existente + `KAFKA_LOG_DIRS=/var/lib/kafka/data`, volumen `kafka_data`, `KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"`, `stop_grace_period: 30s`, mismo `CLUSTER_ID`), `postgres` (`postgres:17.11-alpine`, `${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD en .env: copia .env.example a .env y define una contraseña}`, volumen `postgres_data`, montaje `./db/init:/docker-entrypoint-initdb.d:ro`, healthcheck `pg_isready -h 127.0.0.1`, **sin `ports`**), `producer`, `consumer` (montaje `./catalogo:/catalogo:ro`) y `api` (`127.0.0.1:8000:8000`, `HEALTH_PORT=8000` solo para su healthcheck), cada uno con `environment:` explícito (sin `env_file`; el productor sin `POSTGRES_*`), `command` propio y healthcheck de `common.healthcheck`; **sin** `depends_on` de salud; volúmenes con nombre; actualizar el comentario de cabecera
- [ ] T029 [US1] Validar US1 con [quickstart.md §0–§1](quickstart.md#0-requisitos-y-preparación): tres arranques desde cero ≤ 120 s con cinco `healthy` (SC-001), solo dos puertos (SC-007), esquemas/tablas creados, `/health` y `/status` operativos (recuentos 0 y `ultimo_evento: null`), log del consumidor con `paises=242`, 404 en `/docs`, fallo con nombre de variable sin `.env` o con contraseña vacía; **el consumidor sigue sin procesar mensajes** (esperado hasta US2). Anotar tiempos y salidas para el `verifier`

**Checkpoint**: MVP — la pila arranca, se declara sana y expone salud y estado.

---

## Phase 4: User Story 2 — Prueba de humo de extremo a extremo (P1)

**Objetivo**: un evento sintético recorre producer → Kafka → consumer → PostgreSQL → API con acuse, una transacción, commit de offset tras el commit de BD, idempotencia y cuarentena.

**Prueba independiente**: [quickstart.md §2](quickstart.md#2-prueba-de-humo-us2--sc-002-sc-003-sc-004-sc-010) (SC-002, SC-003, SC-004, SC-010; FR-012).

### Pruebas (primero; deben fallar)

- [ ] T030 [P] [US2] Escribir `backend/tests/unit/test_contrato.py` ([contracts/mensaje-kafka-v1.md](contracts/mensaje-kafka-v1.md)): el ejemplo `tests/fixtures/mensaje_v1_ejemplo.json` es válido; **un caso por cada motivo** de rechazo (`valor_ausente`, `json_ilegible` incl. UTF-8 inválido y `NaN`/`Infinity`, `no_es_objeto`, `campo_ausente` incl. campo desconocido en la raíz, `tipo_invalido`, `schema_version_no_soportada` incl. `"1"`, `true` y `2`, `source_invalido`, `mode_invalido`, `mode_no_corresponde_al_topic` con `replay` en el topic live, `ingested_at_invalido` sin zona o con desplazamiento ≠ 0, `evento_sin_id`, `clave_ausente`, `clave_distinta_de_id`, `updated_invalido` con `true`, `1.5`, `"1"`, negativo y > 4102444800000, `sintetico_inconsistente` en ambos sentidos); orden de comprobación (el primer fallo decide el motivo); `updated` ms → `datetime` UTC exacto (sin `float`); `es_sintetico("synthetic-smoke")` verdadero y `es_sintetico("usgs")` falso; `construir_mensaje()` produce clave UTF-8 = `id`, `ingested_at` con `Z` y milisegundos y sobrevive a `validar_mensaje()`; el evento original no se altera (igualdad profunda)
- [ ] T031 [P] [US2] Escribir `backend/tests/unit/test_evento_sintetico.py`: por defecto `id=synthetic-smoke-0001`, `updated=1767225600000`, `source=synthetic-smoke`, `place` contiene «SINTÉTICO», magnitud no nula y coordenadas válidas; `--unico` añade sufijo `AAAAMMDDThhmmssZ` (reloj inyectado) conservando el prefijo `synthetic-smoke-`; dos llamadas por defecto generan la **misma versión** `(id, updated)`; el mensaje resultante pasa `validar_mensaje()`
- [ ] T032 [P] [US2] Escribir `backend/tests/unit/test_decision_consumidor.py` (sin infraestructura): `decidir(registro, topic_modo)` → `Aceptar(version)` (con `updated` UTC, `sintetico`, esquema destino `live`) o `Rechazar(motivo, detalle)`; `resultado_escritura(rowcount)` → `persistido` (1) / `omitido` (0); `clasificar_error_bd(excepción)` → `reintentar` para `OperationalError`/`InterfaceError`, `cuarentena` para `DataError`/`IntegrityError` (SQLSTATE 22/23) con motivo `no_almacenable`, `desconocido` para el resto (se reintenta con `result=error`); el esquema destino sale de una lista cerrada (`live`/`replay`), nunca de texto libre
- [ ] T033 [P] [US2] Copiar `specs/001-esqueleto/contracts/mensaje-kafka-v1.ejemplo.json` a `backend/tests/fixtures/mensaje_v1_ejemplo.json` (byte a byte; comprobar con `Get-FileHash`)

### Implementación

- [ ] T034 [US2] Implementar `backend/observatorio/common/contrato.py` (T030, T033): `SCHEMA_VERSION = 1`, `MODOS`, `PREFIJO_SINTETICO = "synthetic-"`, `construir_mensaje(evento, source, mode, ingested_at)` → `(clave: bytes, valor: bytes)`, `validar_mensaje(clave, valor, modo_del_topic)` → `MensajeValido` | `Rechazo(motivo, detalle)` con el **orden de comprobación** del contrato; `json.loads(parse_constant=…)` que rechaza `NaN`/`Infinity`; `ms_a_datetime()` con aritmética entera; sin pydantic ni jsonschema
- [ ] T035 [P] [US2] Implementar `backend/observatorio/producer/evento_sintetico.py` (T031, T034): `evento_sintetico(unico=False, ahora=…)` según [contracts/mensaje-kafka-v1.ejemplo.json](contracts/mensaje-kafka-v1.ejemplo.json)
- [ ] T036 [US2] Implementar `backend/observatorio/producer/smoke.py` (T035, T018, T015): `python -m observatorio.producer.smoke [--repeat N] [--unico]`; `ensure_topic()`; `AIOKafkaProducer` propio (`acks="all"`, idempotente); **`result=publicado` solo después de que `send_and_wait` devuelva** (con `event_id`, `updated`, `topic`, `partition`, `offset`); sin acuse en `SMOKE_TIMEOUT_SECONDS` → `result=error reason=sin_acuse`, **sin** `publicado`, salida con código 1
- [ ] T037 [P] [US2] Implementar `backend/observatorio/consumer/decision.py` (T032, T034): funciones puras `decidir`, `resultado_escritura`, `clasificar_error_bd`
- [ ] T038 [US2] Implementar `backend/observatorio/consumer/persistencia.py` (T032, T023, T024): `guardar_version(db, version)` ejecuta **en una sola transacción** `INSERT INTO <esquema>.versiones_evento (event_id, updated, schema_version, source, mode, sintetico, ingested_at, topic, particion, offset_kafka, original) VALUES (…) ON CONFLICT (event_id, updated) DO NOTHING` con `original = Jsonb(mensaje_completo)` y devuelve `cursor.rowcount`; `guardar_cuarentena(db, rechazo, registro)` hace `INSERT INTO ingesta.cuarentena (motivo, detalle, topic, particion, offset_kafka, clave, original) … ON CONFLICT (topic, particion, offset_kafka) DO NOTHING`; el esquema se compone con `psycopg.sql.Identifier` desde la lista cerrada; `processed_at` y `recibido_en` usan el valor por defecto de la BD (`clock_timestamp()`)
- [ ] T039 [US2] Completar el bucle de `backend/observatorio/consumer/app.py` (T037, T038, T027): por registro → `decidir` → transacción (versión **o** cuarentena) → `registrar(result=persistido|omitido|rechazado, event_id, updated, topic, partition, offset, motivo)` → **solo entonces** `consumer.commit({tp: offset + 1})`; error de conexión: **no** confirmar, reconectar con backoff y reintentar el **mismo** registro; `DataError`/`IntegrityError`: revertir, guardar en cuarentena `no_almacenable` con el SQLSTATE en `detalle` en otra transacción; excepción desconocida: `result=error` con `exc` y reintento (nunca avanzar ni descartar en silencio); un fallo del commit del offset (p. ej. reasignación de grupo) se registra como `result=error` y el registro se reentregará
- [ ] T040 [P] [US2] Escribir `scripts/borrar_sinteticos.sql` (`BEGIN; DELETE FROM live.versiones_evento WHERE sintetico; COMMIT;`, con comentario en español de que no toca Kafka ni la cuarentena y de que solo borra `sintetico = true`)
- [ ] T041 [US2] Validar US2 con [quickstart.md §2.1–§2.6](quickstart.md#2-prueba-de-humo-us2--sc-002-sc-003-sc-004-sc-010): publicado→visible ≤ 10 s ×3 (SC-002; el `/status` de US1 ya cuenta y muestra el último evento), reenvío ×5 (SC-003), consumidor detenido/reiniciado (SC-004), PostgreSQL caído con `LAG ≥ 1` y recuperación (US2.4), cuatro mensajes inválidos a cuarentena y reentrega sin duplicar (FR-012), borrado solo de sintéticos con un «real» de control (SC-010). Guardar salidas

**Checkpoint**: US1 + US2 funcionan; el esqueleto cumple las pruebas §11 «Recibir un evento nuevo», «Reenviar la misma versión», «Reiniciar consumidor».

---

## Phase 5: User Story 3 — Dependencias lentas o caídas (P2)

**Objetivo**: ningún servicio termina por una dependencia ausente; reintentos visibles; la salud refleja la situación real y se recupera sola, también **tras** perder la conexión.

**Prueba independiente**: [quickstart.md §3](quickstart.md#3-dependencias-lentas-o-caídas-us3--sc-006) (SC-006).

- [ ] T042 [P] [US3] Escribir `backend/tests/unit/test_supervisor.py` (reloj/sleep/sesión falsos, vía `asyncio.run`): una sesión que lanza al arrancar se reintenta con backoff y registra `result=reintento`; una sesión sana no se reinicia; tras `PROBE_FALLOS_REINICIO` (3) fallos **consecutivos** de la sonda se cancela y recrea la sesión, y un solo fallo aislado no; un éxito de la sonda pone la comprobación en verde y reinicia el contador; `CancelledError` detiene sin reintentar; nunca se invoca `sys.exit`
- [ ] T043 [US3] Implementar `backend/observatorio/common/supervisor.py` (T042, T015, T016): `supervisar(abrir_sesion, sonda, comprobacion, estado, config)` que mantiene una sesión, ejecuta la sonda cada `HEALTH_PROBE_INTERVAL_SECONDS`, actualiza la comprobación (`kafka`, `postgres`) y recrea la sesión con backoff
- [ ] T044 [US3] Integrar el supervisor en `backend/observatorio/producer/app.py`: sonda de metadatos de Kafka; tras pérdida y recuperación vuelve a ejecutar `ensure_topic()` y deja la comprobación `kafka` coherente
- [ ] T045 [US3] Integrar el supervisor en `backend/observatorio/consumer/app.py` (tras T039): una tarea de sonda para PostgreSQL (`SELECT 1` vía `Database.sonda()`; si falla, reconexión con backoff y comprobación `postgres` en rojo) y otra para Kafka (`consumer.topics()` bajo `wait_for`); tras `PROBE_FALLOS_REINICIO` fallos de Kafka se detiene y recrea el `AIOKafkaConsumer` (esperando de nuevo el topic); sin avanzar offsets durante la reconexión; la comprobación `catalogo` no se toca
- [ ] T046 [US3] Integrar la sonda y la reconexión en segundo plano de PostgreSQL en `backend/observatorio/api/main.py` (tras T026): `/health` 503 y `/status` con base `fallida` mientras no haya conexión; recuperación automática sin reiniciar el contenedor
- [ ] T047 [US3] Validar US3 con [quickstart.md §3.1–§3.7](quickstart.md#3-dependencias-lentas-o-caídas-us3--sc-006): arranque con PostgreSQL y con Kafka parados (reintentos 1,2,4,8,16,30,30 s, 0 reinicios de contenedor, `healthy` ≤ 60 s tras volver la dependencia), caída de PostgreSQL en marcha (`unhealthy` ≤ 60 s, `/status` con `fallida` y `null`), **reinicio de Kafka en marcha** (valida RK-01), productor sin acuse (FR-014), ausencia de contraseñas en logs. Si el reinicio de Kafka deja a aiokafka en mal estado, ajustar T044/T045 y **documentarlo en research.md R-13**

**Checkpoint**: US1–US3 completas e independientes.

---

## Phase 6: User Story 4 — Reiniciar la pila sin perder datos (P2)

**Objetivo**: datos de PostgreSQL y mensajes de Kafka sobreviven a `down`/`up`; retención finita, configurable por variable y reconciliada al cambiarla.

**Prueba independiente**: [quickstart.md §4](quickstart.md#4-persistencia-y-retención-us4--sc-005) (SC-005).

- [ ] T048 [P] [US4] Ampliar `backend/tests/unit/test_kafka_topic.py`: `plan_reconciliacion(actual: dict, deseado: dict)` → «sin cambios» si coinciden, «alterar» con los pares a cambiar si difieren (retención y/o `segment.ms`), y aviso `particiones_distintas` si las particiones existentes ≠ configuradas **sin** proponer modificarlas
- [ ] T049 [US4] Implementar en `backend/observatorio/common/kafka.py` la reconciliación (T048): `describe_configs` + `alter_configs` (legacy, envía **siempre** `retention.ms` y `segment.ms`, R-05) cuando el topic ya existe y difiere; log `result=listo component=topic action=topic_creado|topic_reconciliado|topic_conforme retention_ms=… partitions=…`; no verificar con `describe_configs` inmediatamente después (desfase [medido]); la usa `ensure_topic()` desde `producer/app.py` y `producer/smoke.py`
- [ ] T050 [US4] Validar US4 con [quickstart.md §4](quickstart.md#4-persistencia-y-retención-us4--sc-005): `down`/`up` conserva recuento, último evento y mensaje del topic (SC-005); el volumen de Kafka es de `appuser` y los datos están en `/var/lib/kafka/data` (nada en `/tmp`); retención efectiva = `.env` (4.3); cambio a `TOPIC_RETENTION_MS=3600000` + recrear el productor refleja el nuevo valor sin tocar `compose.yaml` (4.4); volúmenes con nombre presentes. Si el volumen diera `Permission denied`, **detenerse** y revisar R-03 antes de tocar `compose.yaml`

**Checkpoint**: US1–US4 completas.

---

## Phase 7: User Story 5 — Catálogo de países cargado al arrancar (P2)

**Objetivo**: el consumidor valida el catálogo al arrancar, registra cuántos países cargó y, si falla, lo dice con el motivo, no consume y queda `unhealthy`. **El código (T012, T019, T027) ya existe desde Foundational/US1**; esta fase valida los escenarios de fallo.

**Prueba independiente**: [quickstart.md §5](quickstart.md#5-catálogo-de-países-us5--sc-008) (SC-008).

- [ ] T051 [US5] Validar US5 con [quickstart.md §5](quickstart.md#5-catálogo-de-países-us5--sc-008): 242 países en ≤ 30 s con el catálogo entregado; escritura rechazada (montaje `./catalogo:/catalogo:ro`; si falta el `:ro` en `compose.yaml`, corregirlo); los seis casos de catálogo ausente/inválido con su motivo (`catalogo_ausente`, `catalogo_ilegible`, `catalogo_vacio`, `geometria_no_poligonal`, `adm0_a3_ausente`, `adm0_a3_repetido`), sin ningún `result=persistido/omitido/rechazado`, sin conexión a PostgreSQL ni Kafka y con la salud nunca `healthy`. Si algún escenario falla, corregir `common/catalogo.py` o `consumer/app.py` con su prueba en `test_catalogo.py` primero

**Checkpoint**: US1–US5 completas.

---

## Phase 8: User Story 6 — Logs, configuración y documentación únicas (P3)

**Objetivo**: logs homogéneos, configuración completa por entorno y un único apartado documental operativo.

**Prueba independiente**: [quickstart.md §6](quickstart.md#6-logs-configuración-y-documentación-us6--sc-009-sc-011) (SC-009, SC-011).

- [ ] T052 [P] [US6] Reescribir en `README.md` un **apartado único «Puertos, listeners y arranque»** con: tabla de puertos publicados y su finalidad (`127.0.0.1:8000` API, `127.0.0.1:9092` Kafka solo inspección; PostgreSQL y puertos de salud **no** publicados); listeners de Kafka (interno `kafka:19092`, host `localhost:9092`) y cuál usar desde dónde; arranque con PowerShell (`Copy-Item .env.example .env`, definir `POSTGRES_PASSWORD`, `docker compose up --build -d`, `docker compose ps`); parada y reinicio sin pérdida (`down` / `up -d`); **`docker compose down -v` es la única orden que borra datos**; retención por defecto (7 días) y cómo cambiarla (`TOPIC_RETENTION_MS`); prueba de humo (`docker compose exec producer python -m observatorio.producer.smoke`, `--repeat`, `--unico`); eliminación de sintéticos (`Get-Content -Raw scripts/borrar_sinteticos.sql | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB'`); aplicar el esquema a un volumen existente (orden de [research.md R-07](research.md#r-07--evolución-del-esquema-sobre-volúmenes-existentes)); tests (`docker compose run --rm --no-deps consumer pytest -q`); conflicto de puertos (`Get-NetTCPConnection`); sustituir el bloque `cp` por PowerShell; actualizar la línea «Estado» y la fila de `001-esqueleto`
- [ ] T053 [P] [US6] Comprobar que `.env.example` enumera **todas** las variables que leen `common/config.py`, `common/healthcheck.py` (solo `HEALTH_PORT`) y `compose.yaml` y que no contiene credenciales: `Select-String -Path backend/observatorio -Pattern 'environ|getenv' -Recurse` frente a la tabla de [contracts/variables-entorno.md](contracts/variables-entorno.md); no debe aparecer `HEALTH_URL`; corregir las discrepancias en `.env.example` (no en el contrato sin avisar)
- [ ] T054 [P] [US6] Revisar `docs/CONTRATO-API.md` frente a `specs/001-esqueleto/contracts/api.openapi.yaml` y a las respuestas reales de `/health` y `/status`; si difieren, **corregir el código o actualizar ambos documentos de forma coherente** (nunca solo uno)
- [ ] T055 [US6] Validar US6 con [quickstart.md §6](quickstart.md#6-logs-configuración-y-documentación-us6--sc-009-sc-011): `invalidas=0` en el análisis de logs de los tres servicios tras la prueba de humo (SC-009), líneas de evento con `event_id` y `updated`, `.env` fuera de Git, contrato de ejemplo sincronizado (`Get-FileHash`), y cronometrar a una persona externa siguiendo solo el README (SC-011 ≤ 15 min)

**Checkpoint**: las seis historias completas.

---

## Phase 9: Polish y transversales

- [ ] T056 Ejecutar `docker compose run --rm --no-deps consumer pytest -q` en la imagen final: todas las pruebas en verde sin Kafka ni PostgreSQL en marcha ([quickstart.md §7](quickstart.md#7-pruebas-unitarias-en-la-imagen-python-312))
- [ ] T057 Ejecutar de principio a fin [quickstart.md §1–§6](quickstart.md) **tres veces** desde cero (`docker compose down -v`) y registrar tiempos y resultados en `specs/001-esqueleto/evidencias/` (SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007, SC-008, SC-009, SC-010)
- [ ] T058 [P] Revisión de seguridad ligera: `docker compose config` no muestra la contraseña en claro en el repositorio; `git grep -n -i "password\|secret" -- . ":!specs" ":!docs"` solo encuentra nombres de variable; ningún log contiene el valor de la contraseña (§3.7); imagen con usuario no root (`docker compose exec consumer id`); solo dos puertos publicados
- [ ] T059 [P] Si cualquier verificación contradice una decisión de [research.md](research.md) o [plan.md](plan.md) (p. ej. RK-01, RK-02), **actualizar primero research/plan** (Constitución, «un cambio de comportamiento MUST actualizar spec o plan antes que el código») y luego el código
- [ ] T060 Entregar al `verifier`: repetir los comandos del quickstart guardando las evidencias en `specs/001-esqueleto/evidencias/`; confirmar que no se ha creado ningún fichero de contexto de agente y que `/speckit-analyze` sigue sin hallazgos CRITICAL/HIGH

---

## Dependencias y orden de ejecución

### Secuencia resultante (una línea)

`F1 Setup (T001–T006) → F2 Foundational: pruebas T007–T012 → impl T013–T019 → T020 → US1: T021–T022 → T023–T029 (db → SQL → producer → API+/status → consumer+catálogo → compose → validar) → US2 (T030–T041) → US3 (T042–T047) → US4 (T048–T050) → US5 validar (T051) → US6 (T052–T055) → Polish (T056–T060)`.

### Dependencias entre fases

- **Setup (F1)** → sin dependencias.
- **Foundational (F2)** → depende de F1; **bloquea** todas las historias. Incluye el cargador del catálogo (T012, T019).
- **US1 (F3)** → depende de F2. Es el MVP: `/health` + `/status` + catálogo + cinco servicios sanos.
- **US2 (F4)** → depende de US1 (necesita `compose.yaml`, `db.py`, esquema SQL, `/status` y los esqueletos de los servicios).
- **US3 (F5)** → depende de US1 y de US2 en `consumer/app.py`.
- **US4 (F6)** → depende de US1 y de T018; la validación (T050) necesita US2 (hay que publicar el sintético).
- **US5 (F7)** → solo validación; depende de US1 (T027, T028). Puede ejecutarse en cuanto exista la pila, incluso antes de US2.
- **US6 (F8)** → T052 necesita que existan las órdenes de US1–US4 para documentarlas; T055 necesita US2 (logs de evento).
- **Polish (F9)** → depende de todas las historias.

### Ficheros compartidos (orden obligatorio)

- `consumer/app.py`: T027 (US1: catálogo + esqueleto) → T039 (US2: bucle) → T045 (US3: sondas/supervisor).
- `api/main.py`: T026 (US1: `/health` + `/status`) → T046 (US3: sonda/reconexión).
- `producer/app.py`: T025 (US1) → T044 (US3); `common/kafka.py`: T018 (F2) → T049 (US4).
- `compose.yaml`: T028 (y T051 si hace falta corregir el `:ro`).

### Oportunidades de paralelismo

- F1: T002–T005 en paralelo tras T001.
- F2: las seis pruebas T007–T012 en paralelo; luego T014, T015, T016 y T019 en paralelo (T013, T017 y T018 con sus dependencias).
- US1: T021 ‖ T022 ‖ T024; T025 ‖ T026 tras T023.
- US2: T030–T033 en paralelo; T035 ‖ T037 ‖ T040 tras T034.
- US3: T042 puede escribirse mientras se cierra US2.
- US6: T052 ‖ T053 ‖ T054.

### Ejemplo de paralelismo (US2, pruebas)

```text
Task: "Escribir backend/tests/unit/test_contrato.py"
Task: "Escribir backend/tests/unit/test_evento_sintetico.py"
Task: "Escribir backend/tests/unit/test_decision_consumidor.py"
Task: "Copiar el ejemplo a backend/tests/fixtures/mensaje_v1_ejemplo.json"
```

---

## Estrategia de implementación

### MVP primero (US1)

1. F1 Setup → F2 Foundational (todo en verde con pytest en la imagen).
2. F3 US1 → **parar y validar** con quickstart §1: cinco servicios `healthy`, dos puertos, esquemas creados, catálogo con 242 países, `/status` operativo.
3. Demostrable ya: pila reproducible (Enunciado §2, §9).

### Entrega incremental

1. + US2 → la prueba de humo valida las garantías de la Constitución III (acuse, transacción, offset, idempotencia) y la cuarentena. **Este es el verdadero cierre del esqueleto.**
2. + US3 → resiliencia real (incluida la pérdida de conexión en marcha).
3. + US4 → retención reconciliada y persistencia verificada.
4. + US5 → escenarios de catálogo ausente/corrupto validados.
5. + US6 → documentación única y auditoría de logs.
6. F9 Polish con evidencias.

### Un único desarrollador (caso real)

Orden recomendado: el de la secuencia de arriba. Un commit por tarea o grupo lógico (p. ej. «Añade el contrato v1 y sus pruebas»).

## Notas

- Las tareas con «Validar» ejecutan comandos reales y guardan evidencia; no son código.
- Verificar que las pruebas **fallan** antes de implementar (Constitución, «Flujo de trabajo»).
- No añadir dependencias fuera de R-02 sin justificarlas antes en `research.md` (Constitución VIII).
- Si un riesgo de [research.md](research.md#riesgos-y-puntos-abiertos) se materializa, parar y actualizar el diseño antes de seguir.
