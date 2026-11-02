# Implementation Plan: Esqueleto de extremo a extremo (walking skeleton)

**Branch**: `001-esqueleto` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-esqueleto/spec.md` (FR-012 modificado: cuarentena persistente mínima desde el esqueleto)

## Summary

Los cinco servicios obligatorios (`kafka`, `postgres`, `producer`, `consumer`, `api`) arrancan con
`docker compose up --build -d`, se declaran sanos solo con sus conexiones establecidas y se
recuperan solos de dependencias lentas o caídas. Una orden de **prueba de humo** publica un
evento SINTÉTICO conforme al **contrato Kafka v1** que recorre
producer → Kafka → consumer → PostgreSQL → API con publicación tras acuse, escritura en una
transacción, commit manual del offset después del commit de BD, idempotencia por
`(event_id, updated)` y cuarentena persistente para lo que incumple el contrato.

Enfoque técnico (decisiones y alternativas en [research.md](research.md)):

- Un único paquete Python `observatorio/` en `backend/` (una imagen `python:3.12-slim`, tres
  comandos distintos) con `common/` (config por entorno, logs `clave=valor`, contrato v1,
  reintentos con backoff, salud, acceso a BD, catálogo, utilidades de Kafka).
- `psycopg` 3 asíncrono como único driver (R-01); `aiokafka` 0.15.0 con
  `acks=all` y commit manual (R-15).
- Kafka con volumen en `/var/lib/kafka/data` (ruta declarada por la imagen, verificada),
  auto-creación de topics desactivada y topic creado/reconciliado por el productor (R-03–R-05).
- PostgreSQL 17 con esquemas `live`, `replay`, `ingesta`, inicializados por `db/init/` y
  evolución por SQL idempotente + `ingesta.version_esquema` (R-06, R-07).
- Salud real por HTTP interno (no publicado) con sondas activas y supervisores de sesión (R-12, R-13).
- La lógica crítica (contrato, backoff, logs, catálogo, decisión del consumidor) son funciones
  puras con pruebas unitarias que se escriben **antes** de la implementación (R-17).

## Technical Context

**Language/Version**: Python 3.12 (imagen `python:3.12-slim`; el host tiene 3.13, por eso las pruebas se ejecutan en la imagen)

**Primary Dependencies**: `aiokafka==0.15.0`, `fastapi==0.162.0`, `uvicorn==0.54.0`, `psycopg[binary]==3.3.6`, `shapely==2.2.0`, `pytest==9.2.0` (justificación y exclusiones en R-02)

**Storage**: PostgreSQL 17.11 (volumen `postgres_data`); Kafka 4.1.2 KRaft de un nodo (volumen `kafka_data`); catálogo `catalogo/paises.geojson` montado en solo lectura

**Testing**: `pytest` en `backend/tests/` ejecutado dentro de la imagen (`docker compose run --rm --no-deps consumer pytest -q`); pruebas de integración como pasos verificables en [quickstart.md](quickstart.md)

**Target Platform**: Docker Compose v2 sobre Windows + PowerShell (contenedores Linux)

**Project Type**: pila de servicios con backend Python único (sin frontend en esta feature)

**Performance Goals**: pila «healthy» ≤ 120 s desde clon limpio (SC-001); evento sintético visible en la API ≤ 10 s (SC-002); recuperación de dependencia ≤ 60 s (SC-006)

**Constraints**: solo `127.0.0.1:8000` y `127.0.0.1:9092` publicados; PostgreSQL y puertos de salud internos sin publicar; sin secretos en Git ni en logs; direcciones entre servicios por nombre de servicio (`kafka:19092`, `postgres:5432`)

**Scale/Scope**: ≈ 1 mensaje sintético; un nodo, una partición asignada por mensaje (3 particiones, 1 consumidor). Capacidad real de USGS (~10² eventos/hora) y del histórico se miden en 004/007

## Constitution Check

*GATE: debe pasar antes de la investigación (Fase 0) y revalidarse tras el diseño (Fase 1).*

| Principio | Cómo lo cumple este plan | Estado |
| --- | --- | --- |
| **I. Entorno reproducible en Compose** | Cinco servicios en `compose.yaml`; imagen Python única con dependencias `==`; healthcheck en los cinco (HTTP real, `pg_isready` por TCP, check de Kafka existente); backoff 1→30 s al arrancar y tras perder la conexión, sin `depends_on: service_healthy` (R-13); volúmenes `kafka_data` y `postgres_data`; retención finita (7 días, variable); direcciones por nombre de servicio | ✅ |
| **II. Contrato explícito y versionado** | Contrato v1 en [contracts/](contracts/) (esquema, ejemplo y reglas) con `contrato.py` compartido por productor y consumidor; clave = `id`; rechazo de `schema_version` ≠ 1; reglas de compatibilidad escritas. `docs/CONTRATO-API.md` creado con `/health` y `/status` | ✅ |
| **III. Al menos una vez + escritura idempotente (NO NEGOCIABLE)** | `publicado` solo tras `send_and_wait`; una transacción por mensaje; commit del offset después del commit de BD; `PRIMARY KEY (event_id, updated)` + `ON CONFLICT DO NOTHING`; el historial no se sobrescribe. «Estado actual solo con `updated` más reciente» y agregaciones desde el estado actual **no aplican aún** (spec: feature 003); los recuentos de 001 son sobre versiones guardadas y se declaran como provisionales (R-19) | ✅ (alcance acotado por la spec) |
| **IV. Trazabilidad y calidad explícita** | Cuarentena persistente con motivo, posición Kafka y bytes originales (R-09); fallos de dato → cuarentena, nunca descarte silencioso; todo instante en `timestamptz` UTC separando `updated`, ingesta y procesamiento. Conservación del GeoJSON crudo de cada extracción, reglas de validación del contenido USGS y exclusión por `type` son de 002/003 (**fuera de alcance, sin USGS en 001**) | ✅ (alcance acotado) |
| **V. Integración geográfica por geometría** | Solo se carga y valida el catálogo (`ADM0_A3` único, Polygon/MultiPolygon) con Shapely al arrancar; no se asigna país (003) | ✅ |
| **VI. Aislamiento de replay y sintéticos** | Esquema `replay` reservado y separado; `mode=replay` en el topic live se rechaza; sintético = `source`/`id` con prefijo `synthetic-` + `CHECK` en BD + recuentos separados + procedimiento de borrado que solo toca `sintetico` | ✅ |
| **VII. Superficie mínima y sin secretos** | Publicados solo `127.0.0.1:8000` y `127.0.0.1:9092`; PostgreSQL y `HEALTH_PORT` no publicados; `/health` y `/status` públicos con datos agregados, sin `/docs` ni `openapi.json`; contraseña obligatoria desde `.env` (ignorado); `.env.example` sin credenciales; el productor no recibe credenciales de BD; logs sin secretos (R-14); API en `0.0.0.0:8000` HTTP | ✅ |
| **VIII. Simplicidad y evidencia** | Sin Spark/Flink/K8s/ML; cada dependencia justificada y cada exclusión registrada (R-02, R-10, R-12, R-14, R-17); sin ORM, sin pool, sin herramienta de migraciones, sin sexto servicio; evidencia = pytest + pasos de quickstart ligados a SC-001…SC-011 y a las pruebas del §11 («Recibir un evento nuevo», «Reenviar la misma versión», «Reiniciar consumidor») | ✅ |
| **Restricciones de plataforma** | Python 3.12, aiokafka/psycopg/shapely/fastapi/uvicorn; Kafka 4.1 KRaft, listeners `kafka:19092` y `localhost:9092`; esquema inicial en `db/init/`; índices justificados en [data-model.md](data-model.md); logs con servicio, `event_id`, versión y resultado | ✅ |

**Resultado de la puerta (pre-investigación)**: sin violaciones.
**Reevaluación tras el diseño (Fase 1)**: sin violaciones nuevas. Puntos que merecen atención
del `verifier` y no son violaciones: (a) los recuentos de `/status` cuentan sobre versiones
guardadas hasta que la 003 cree el estado actual; (b) la API usa el mismo rol de BD que el
consumidor (RK-06).

## Project Structure

### Documentation (this feature)

```text
specs/001-esqueleto/
├── spec.md
├── plan.md                                   # Este fichero
├── research.md                               # Decisiones R-01…R-23, alternativas y riesgos
├── data-model.md                             # Modelo conceptual, lógico y físico; índices; complejidad
├── quickstart.md                             # Pasos verificables (para el verifier)
├── contracts/
│   ├── mensaje-kafka-v1.md                   # Contrato en prosa: campos, motivos de rechazo, compatibilidad
│   ├── mensaje-kafka-v1.schema.json          # JSON Schema (documentación)
│   ├── mensaje-kafka-v1.ejemplo.json         # Ejemplo (copia en backend/tests/fixtures/)
│   ├── api.openapi.yaml                      # /health y /status
│   ├── logs.md                               # Formato clave=valor y conjunto cerrado de result
│   └── variables-entorno.md                  # Variables, defectos, origen
├── tasks.md                                  # Generado por /speckit-tasks
└── evidencias/                               # Lo rellena el verifier
```

Fuera de `specs/`: `docs/CONTRATO-API.md` (creado en esta fase; exigido por la Constitución II).

### Source Code (repository root)

Estructura **resultante** (lo marcado con `*` ya existe y se modifica; el resto lo crea
`developer` según [tasks.md](tasks.md)):

```text
compose.yaml *                      # Kafka + postgres + producer + consumer + api, volúmenes
.env.example                        # Plantilla sin credenciales (contracts/variables-entorno.md)
README.md *                         # Apartado único «Puertos, listeners y arranque»
.gitignore *                        # (ya ignora .env, se verifica)
backend/
├── Dockerfile                      # python:3.12-slim, usuario no root, una sola imagen
├── .dockerignore
├── requirements.txt                # Versiones fijadas con ==
├── pytest.ini
├── observatorio/
│   ├── __init__.py
│   ├── common/
│   │   ├── config.py               # Ajustes por servicio desde el entorno, ConfigError, secretos ocultos
│   │   ├── logging.py              # Formateador clave=valor, registrar(), redacción de secretos
│   │   ├── retry.py                # esperas() / reintentar() con backoff exponencial
│   │   ├── health.py               # Estado de comprobaciones + servidor HTTP asyncio
│   │   ├── healthcheck.py          # CLI del healthcheck de Compose (GET /health → exit 0/1)
│   │   ├── contrato.py             # Contrato v1: construir/validar mensaje, motivos, sintético
│   │   ├── db.py                   # Database: conexión con backoff, sonda, guarda de versión de esquema
│   │   ├── kafka.py                # ensure_topic, wait_for_topic, sondas de Kafka
│   │   ├── supervisor.py           # Sesión supervisada: sondas periódicas y recreación con backoff (US3)
│   │   └── catalogo.py             # Carga y validación del catálogo con Shapely
│   ├── producer/
│   │   ├── __main__.py / app.py    # Supervisor: Kafka → ensure_topic → salud → reposo (002 añadirá USGS)
│   │   ├── evento_sintetico.py     # Construcción del evento sintético de la prueba de humo
│   │   └── smoke.py                # python -m observatorio.producer.smoke
│   ├── consumer/
│   │   ├── __main__.py / app.py    # Catálogo → BD → espera de topic → consumo con commit manual
│   │   ├── decision.py             # Función pura: persistido / omitido / rechazado / no_almacenable
│   │   └── persistencia.py         # SQL de versiones y cuarentena, una transacción por mensaje
│   └── api/
│       ├── __main__.py             # uvicorn con log_config=None y access_log=False
│       ├── main.py                 # FastAPI (/health, /status), sin /docs
│       └── estado.py               # Consultas y armar_estado() puro
└── tests/
    ├── fixtures/mensaje_v1_ejemplo.json
    └── unit/                       # test_config, test_logging, test_retry, test_health,
                                    # test_kafka_topic, test_db, test_contrato,
                                    # test_evento_sintetico, test_decision_consumidor,
                                    # test_catalogo, test_estado_api, test_supervisor
db/
└── init/001_esquema_base.sql       # Esquemas, tablas, índices, versión de esquema (idempotente)
scripts/
├── descargar_paises.py *           # (existente, sin cambios)
└── borrar_sinteticos.sql           # Elimina solo filas sintéticas
catalogo/paises.geojson *           # (existente; se monta en /catalogo:ro)
docs/CONTRATO-API.md                # /health y /status
```

**Structure Decision**: backend único con paquete `observatorio/` y tres subpaquetes de servicio
más `common/`, tal como se decidió; sin directorio `frontend/` (feature 006). `scripts/` y
`db/` en la raíz según la estructura acordada del proyecto.

## Diseño de `compose.yaml`

| Servicio | Imagen / build | Puertos publicados | Volúmenes | Healthcheck | Variables (resumen) |
| --- | --- | --- | --- | --- | --- |
| `kafka` | `apache/kafka:4.1.2` | `127.0.0.1:9092:9092` | `kafka_data:/var/lib/kafka/data` | existente: `kafka-broker-api-versions.sh --bootstrap-server localhost:9092` (5 s, 24 reintentos, 25 s de gracia) | listeners `INTERNAL://kafka:19092` y `HOST://localhost:9092`; `CLUSTER_ID` fijo; `KAFKA_LOG_DIRS=/var/lib/kafka/data`; `KAFKA_AUTO_CREATE_TOPICS_ENABLE=false`; `stop_grace_period: 30s` |
| `postgres` | `postgres:17.11-alpine` | **ninguno** | `postgres_data:/var/lib/postgresql/data`; `./db/init:/docker-entrypoint-initdb.d:ro` | `pg_isready -h 127.0.0.1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"` (5 s, 10 reintentos, 20 s de gracia) | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?…}` |
| `producer` | `x-backend` (`observatorio-backend:local`) | **ninguno** | — | `python -m observatorio.common.healthcheck` (10 s, timeout 5 s, 3 reintentos, 30 s de gracia) | Kafka, topic, retención, backoff, sonda, log; **sin** `POSTGRES_*` |
| `consumer` | ídem | **ninguno** | `./catalogo:/catalogo:ro` | ídem | Kafka, topic, grupo, `POSTGRES_*`, `CATALOGO_PATH`, backoff, sonda, log |
| `api` | ídem | `127.0.0.1:8000:8000` | — | ídem apuntando a `:8000` | `POSTGRES_*`, backoff, sonda, log |

Comunes: `restart: unless-stopped`; **sin** `depends_on` de salud; `command` distinto por servicio
(`python -m observatorio.producer|consumer|api`); sin `env_file`; volúmenes con nombre
`kafka_data` y `postgres_data`; red por defecto del proyecto. Orden de arranque no garantizado a
propósito (R-13).

## Flujos clave

### Arranque del productor

1. `iniciado` → servidor de salud (todas las comprobaciones en rojo).
2. Conectar con Kafka (`AIOKafkaAdminClient`) con backoff → `ensure_topic()` (crear o
   reconciliar `retention.ms`/`segment.ms`) → `listo component=topic`.
3. Crear `AIOKafkaProducer` (`acks=all`, idempotente) → comprobación `kafka` en verde.
4. Reposo con sonda periódica; tras `PROBE_FALLOS_REINICIO` fallos, recrear la sesión (002 sustituirá el
   reposo por el ciclo de USGS).

### Arranque del consumidor

1. `iniciado` → servidor de salud → **cargar y validar catálogo** (primeros segundos; si falla,
   `result=error motivo=…`, `catalogo` en rojo y **no se consume**; el proceso sigue vivo).
2. Conectar con PostgreSQL (backoff) y comprobar `version_esquema` ≥ 1.
3. Esperar a que exista el topic (R-04) → crear `AIOKafkaConsumer` (`enable_auto_commit=False`,
   `auto_offset_reset=earliest`) → `kafka` y `postgres` en verde.
4. Bucle: `getone` → `decidir()` → transacción (insert versión **o** cuarentena) → log → `commit(offset+1)`.

### Procesamiento de un mensaje (garantía de la Constitución III)

`recibir → validar → BEGIN → INSERT … ON CONFLICT DO NOTHING → COMMIT → log → commit(offset+1)`.
Caída antes de `COMMIT`: no se avanza el offset, se reentrega. Caída entre `COMMIT` y commit del
offset: se reentrega y resulta `omitido`. Detalle en [data-model.md §7](data-model.md#7-ciclo-de-vida-de-un-registro-kafka-transiciones).

### Prueba de humo

`docker compose exec producer python -m observatorio.producer.smoke [--repeat N] [--unico]` →
`ensure_topic()` → `send_and_wait` (clave = `id`) → `result=publicado` (o `result=error` y salida 1 si no hay acuse en `SMOKE_TIMEOUT_SECONDS`).

## Trazabilidad requisito → artefacto

| Requisito | Dónde se resuelve |
| --- | --- |
| FR-001, 002, 003, 006, 022, 025 | `compose.yaml`, `backend/Dockerfile`, R-13, R-16 |
| FR-004, 005 | `common/health.py`, `common/retry.py`, `common/db.py`, `common/kafka.py`, supervisores; R-12, R-13 |
| FR-007, 008 | volúmenes en `compose.yaml`; `common/kafka.py::ensure_topic`; R-03, R-05 |
| FR-009 | `db/init/001_esquema_base.sql`; data-model; R-06, R-07 |
| FR-010, 011 | `common/contrato.py`; `contracts/mensaje-kafka-v1.*` |
| FR-012 | `consumer/decision.py`, `consumer/persistencia.py`, `ingesta.cuarentena`; R-09 |
| FR-013, 014 | `producer/smoke.py`, `producer/evento_sintetico.py`; R-11 |
| FR-015, 016, 017, 018 | `consumer/persistencia.py`, `consumer/app.py`, `live.versiones_evento`; R-15, R-21 |
| FR-019 | columna/`CHECK` `sintetico`, `scripts/borrar_sinteticos.sql`, `/status` |
| FR-020, 021 | `common/catalogo.py`; R-18 |
| FR-023, 024 | `api/main.py`, `api/estado.py`; `contracts/api.openapi.yaml`; R-19 |
| FR-026 | `common/config.py`, `.env.example`; `contracts/variables-entorno.md` |
| FR-027 | `common/logging.py`; `contracts/logs.md` |
| FR-028 | `README.md` (apartado único); R-22 |

## Operaciones clave y complejidad (apartado 10)

Resumen; tabla completa en [data-model.md §6](data-model.md#6-complejidad-de-las-operaciones-clave-insumo-del-apartado-10).

- Búsqueda/inserción de versión por `(event_id, updated)`: B-tree, **O(log n)** medio y peor.
- Último evento procesado: índice descendente, **O(log n)** (sin él, O(n)).
- Recuento de eventos: **O(n)** hasta que la 003 lo sustituya por el estado actual.
- Carga del catálogo: **O(V)** en vértices; unicidad de `ADM0_A3` con `set`, **O(P)** medio.
- Backoff: espera `min(1·2^k, 30)`, **O(1)** por intento; tiempo hasta recuperar ≤ tope + intervalo de sonda + intervalo del healthcheck.

## Complexity Tracking

Sin violaciones de la Constitución que justificar. Elementos de complejidad deliberada y su
justificación (para la defensa):

| Elemento | Por qué es necesario | Alternativa más simple rechazada porque… |
| --- | --- | --- |
| Servidor HTTP de salud propio (≈ 30 líneas) | FR-004 exige salud real por conexión en productor y consumidor, que no tienen HTTP | Un chequeo TCP o un fichero no refleja Kafka/PostgreSQL/catálogo (R-12) |
| Sondas activas + supervisor de sesión | FR-005: recuperarse «tras una pérdida de conexión» sin reiniciar el contenedor | Esperar a que aiokafka/psycopg se enteren: un consumidor ocioso no detecta la pérdida (R-13) |
| `ingesta.version_esquema` + guarda | Defender la evolución del esquema sin herramienta de migraciones | `down -v` pierde datos; Alembic es desproporcionado (R-07) |
| `CHECK` de coherencia sintética en BD | Defensa en profundidad de la Constitución VI | Confiar solo en el validador permitiría contaminar recuentos reales por un fallo de código (R-10) |
| `segment.ms` acotado | Hacer cierta la retención configurada | Con el valor por defecto un mensaje puede vivir el doble de la retención (R-05) |
