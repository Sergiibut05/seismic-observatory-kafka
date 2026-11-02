# Research: Esqueleto de extremo a extremo (001-esqueleto)

**Fecha**: 2026-11-02 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Cada decisión lleva alternativas descartadas y motivo, para que pueda defenderse
de forma individual (Constitución, «Flujo de trabajo»). Las comprobaciones
marcadas como **[medido]** se hicieron el 2026-11-02 contra `apache/kafka:4.1.2`,
`python:3.12-slim` y PyPI; el resto procede de la documentación (Context7).
No quedan «NEEDS CLARIFICATION» abiertos; los riesgos residuales están al final.

## Índice de decisiones

| ID | Decisión | Respuesta corta |
| --- | --- | --- |
| R-01 | Driver PostgreSQL | `psycopg` 3 (async), un único driver |
| R-02 | Versiones fijadas | Tabla de R-02 (verificadas en PyPI) |
| R-03 | Ruta de datos de Kafka | `/var/lib/kafka/data` en volumen `kafka_data` |
| R-04 | Auto-creación de topics | Desactivada; el consumidor espera al topic |
| R-05 | Creación y retención del topic | El productor crea/reconcilia `retention.ms` y `segment.ms` |
| R-06 | Nombres de esquemas y de objetos | `live`, `replay`, `ingesta`; tablas propias en español |
| R-07 | Evolución del esquema | SQL idempotente en `db/init/` + `ingesta.version_esquema` + guarda al conectar |
| R-08 | Imagen y healthcheck de PostgreSQL | `postgres:17.11-alpine`, `pg_isready` por TCP |
| R-09 | Cuarentena mínima | `bytea` + `UNIQUE (topic, particion, offset_kafka)` |
| R-10 | Contrato v1 y su validación | Validador propio sin dependencias; sintético por `source` |
| R-11 | Prueba de humo | Módulo `observatorio.producer.smoke` vía `docker compose exec` |
| R-12 | Salud de los servicios | HTTP interno en `asyncio` + sondas activas |
| R-13 | Reintentos y supervisión | Backoff 1→30 s, supervisor, sin `depends_on: service_healthy` |
| R-14 | Logs `clave=valor` | Formateador propio; uvicorn sin su log_config |
| R-15 | Transacción y commit de offset | Una transacción por mensaje; commit manual después |
| R-16 | Compose: una imagen, entorno explícito | Ancla YAML, sin `env_file` |
| R-17 | Estrategia de pruebas | pytest en la imagen; sin pytest-asyncio ni httpx |
| R-18 | Catálogo de países | Validación con Shapely al arrancar, solo lectura |
| R-19 | Superficie de la API | Sin `/docs` ni `/openapi.json`; `/status` siempre 200 |
| R-20 | Rol único de base de datos | Diferido a la feature 005 |
| R-21 | Posición inicial del grupo | `auto_offset_reset=earliest` |
| R-22 | Dónde vive la documentación operativa | `README.md` |
| R-23 | Fichero de contexto de agente | No se crea ni se actualiza |

---

## R-01 · Driver de PostgreSQL: `psycopg` 3 frente a `asyncpg`

- **Decisión**: `psycopg[binary]==3.3.6` en consumidor y API. Un único driver.
- **Motivo**:
  1. La misma librería ofrece API síncrona y asíncrona. Los notebooks de la
     feature 007, los scripts de carga del histórico (004) y las consultas de
     verificación reutilizan el mismo código y las mismas reglas de adaptación
     de tipos sin segundo driver.
  2. Transacciones explícitas y legibles: `async with conn.transaction():`
     (documentación de psycopg). Con autocommit de conexión y bloques
     `transaction()` se ve dónde empieza y acaba cada commit, que es el punto
     crítico de la Constitución III.
  3. `Jsonb(...)` adapta el mensaje original a `jsonb` sin registrar códecs, y
     los parámetros son `%s` (no `$1`), compatibles con `psycopg.sql` para
     componer el nombre del esquema (`live`/`replay`) con `sql.Identifier`.
  4. `psycopg-binary` trae `libpq` en la rueda: la imagen `python:3.12-slim` no
     necesita `apt-get`.
  5. `rowcount` tras `INSERT … ON CONFLICT DO NOTHING` vale 1 o 0, que es
     exactamente la señal «persistido» frente a «omitido (duplicado)».
- **Alternativas descartadas**:
  - `asyncpg` 0.32.0: más rápido (protocolo binario), pero solo asíncrono (hay
    que añadir otro driver para notebooks/scripts), exige códecs para `jsonb`
    y usa `$1`. Con ~1 mensaje/s la diferencia de rendimiento es irrelevante;
    se mencionará como ventaja en el informe de rendimiento (apartado 10).
  - Los dos a la vez: dos modelos de errores y de transacciones sin beneficio
    (Constitución VIII).
  - SQLAlchemy/ORM: complejidad sin necesidad; el esquema son tres tablas.
- **Pool**: no se usa `psycopg_pool` en esta feature. El consumidor es secuencial
  (una conexión) y la API sirve dos endpoints ligeros con una conexión
  protegida por un `asyncio.Lock`. El pool se evaluará en la feature 005, cuando
  haya consultas concurrentes (nueva dependencia = nueva justificación).
- **Credenciales**: la conexión se abre con parámetros por separado
  (`host=`, `user=`, `password=`…), nunca con una URL, para que contraseñas con
  caracteres especiales no necesiten codificarse y para que no exista una
  «cadena de conexión» que pueda acabar en un log (FR, SC-009).

## R-02 · Versiones fijadas (verificadas en PyPI el 2026-11-02)

| Paquete | Versión | Python requerido | Uso |
| --- | --- | --- | --- |
| `aiokafka` | `0.15.0` | ≥ 3.11 | productor, consumidor, cliente admin |
| `fastapi` | `0.162.0` | ≥ 3.10 | API |
| `uvicorn` | `0.54.0` | ≥ 3.10 | servidor ASGI (sin extras `standard`) |
| `psycopg[binary]` | `3.3.6` | ≥ 3.10 | consumidor y API (R-01) |
| `shapely` | `2.2.0` | ≥ 3.11 | validación del catálogo |
| `pytest` | `9.2.0` | ≥ 3.10 | pruebas unitarias |

- Imagen base: `python:3.12-slim` (decisión previa; cumple todos los mínimos).
- `fastapi` arrastra `pydantic` y `starlette`; no se declaran aparte.
- **Dependencias NO añadidas**: `pytest-asyncio` y `httpx` (R-17),
  `psycopg_pool` (R-01), `jsonschema`/`pydantic` para el contrato (R-10),
  `structlog`/`python-json-logger` (R-14), `aiohttp` (R-12), `curl` en la imagen.
- **Limitación aceptada**: `requirements.txt` fija las dependencias directas con
  `==`; las transitivas flotan. Es suficiente para esta feature y se anota como
  riesgo. Fijarlas todas (fichero de restricciones generado con `pip freeze`)
  es una mejora posible si la reproducibilidad lo exige en la feature 007.
- **Compatibilidad aiokafka 0.15.0 ↔ Kafka 4.1.2 [medido]**: crear topic con
  `retention.ms`, `send_and_wait` con `acks=all`, `AIOKafkaConsumer` con grupo y
  commit manual, `fetch_all_metadata()` y `topics()` funcionan contra el broker
  4.1.2 con `KAFKA_AUTO_CREATE_TOPICS_ENABLE=false`.

## R-03 · Ruta de datos de Kafka: `/var/lib/kafka/data`

- **Decisión**: `KAFKA_LOG_DIRS=/var/lib/kafka/data` y volumen con nombre
  `kafka_data:/var/lib/kafka/data`. `CLUSTER_ID` fijo (`4L6g3nShT-eMCtK--X86sw`).
- **Evidencia [medido]**:
  - `docker image inspect apache/kafka:4.1.2` → `User=appuser` y
    `Volumes={/var/lib/kafka/data, /etc/kafka/secrets, /mnt/shared/config}`: la
    imagen **declara** `/var/lib/kafka/data` como directorio de datos.
  - El `server.properties` por defecto de la imagen trae
    `log.dirs=/tmp/kraft-combined-logs`: **sin tocar nada, los datos viven en
    `/tmp` del contenedor y no persisten** (es lo que tiene hoy `compose.yaml`).
  - Un volumen con nombre montado en `/var/lib/kafka/data` hereda la propiedad de
    la imagen: `drwxrwxr-x appuser root` y `touch` funciona como `uid=1000(appuser)`.
  - El mismo volumen montado en una ruta inexistente en la imagen (`/data/kafka`)
    queda `root:root 755` y `touch` falla con `Permission denied`: es el fallo
    que había que evitar.
- **Efecto sobre KRaft**: el directorio de metadatos (`metadata.log.dir`) toma el
  primer valor de `log.dirs`, de modo que también persiste la identidad del
  clúster; por eso `CLUSTER_ID` debe ser fijo (un volumen formateado con otro
  ID impide arrancar). El script de arranque de la imagen formatea con
  `--ignore-formatted`, así que reiniciar con volumen existente es seguro.
- **Alternativas descartadas**:
  - Montar en `/tmp/kraft-combined-logs` (la ruta actual): no es un `VOLUME`
    declarado; el propietario depende de cómo Docker cree el punto de montaje
    y mezcla datos con `/tmp`.
  - Ruta propia (`/data/kafka`) + `chown` mediante un servicio `init` o
    `user: root`: añade un sexto servicio o ejecuta Kafka como root.
  - Bind mount a una carpeta del repositorio: en Windows/WSL2 los permisos de
    UID 1000 no son fiables y ensucia el árbol de trabajo.
- Se fija `stop_grace_period: 30s` para que el cierre ordenado de Kafka no se
  corte a los 10 s por defecto (evita recuperación de logs en cada `down`).

## R-04 · Auto-creación de topics desactivada

- **Decisión**: `KAFKA_AUTO_CREATE_TOPICS_ENABLE=false`. El productor es el único
  propietario del topic `eventos.live`; el consumidor espera a que exista.
- **Motivo**:
  1. Con auto-creación activa, un consumidor que se suscribe a un topic aún
     inexistente lo **crearía con la retención por defecto del broker**,
     ignorando `TOPIC_RETENTION_MS` (FR-008: «el topic existe, con esa retención,
     antes de la primera publicación»).
  2. Un nombre de topic mal escrito en `.env` crearía en silencio un topic
     huérfano en lugar de fallar de forma visible.
  3. Hace explícito y testeable quién crea qué.
- **Qué no afecta [medido]**: los topics internos (`__consumer_offsets`) se
  siguen creando solos; con la auto-creación desactivada el grupo de consumo
  funcionó (tras unos avisos transitorios `GroupCoordinatorNotAvailable` en el
  primer arranque, que aiokafka reintenta).
- **Cómo espera el consumidor**: antes de crear el `AIOKafkaConsumer`, un bucle con
  backoff llama a `AIOKafkaAdminClient.list_topics()` hasta ver el topic y
  registra `result=reintento reason=topic_no_existe attempt=… wait_s=…`.
  Se evita suscribirse a un topic inexistente porque aiokafka refrescaría los
  metadatos solo cada `metadata_max_age_ms` (5 min por defecto) y tardaría en
  descubrirlo.
- **Alternativas descartadas**:
  - Dejar auto-creación activa: incumple el motivo 1.
  - Servicio `kafka-init` que crea el topic: sexto servicio (FR-001 pide cinco).
  - Topic creado por script del anfitrión: rompe «un comando de arranque».
  - Que el consumidor cree el topic: duplica la lógica y quita la propiedad única.

## R-05 · Creación y reconciliación del topic (`retention.ms`, `segment.ms`)

- **Decisión**: al arrancar (y en cada reconexión), el productor ejecuta
  `ensure_topic()`:
  1. `create_topics([NewTopic(TOPIC_LIVE, TOPIC_PARTITIONS, 1, topic_configs=…)])`
     con `retention.ms = TOPIC_RETENTION_MS` (7 días por defecto) y
     `segment.ms = min(TOPIC_RETENTION_MS, 86400000)`.
  2. Si ya existe, compara con `describe_configs` y, si difiere, aplica
     `alter_configs` (acción `topic_reconciliado`). Así «cambiar la retención en
     `.env` y recrear el productor» surte efecto sin tocar `compose.yaml`
     (US4, escenario 3).
  3. Si las particiones configuradas difieren de las existentes, **no** se
     modifican (no se pueden reducir y cambiarlas altera el reparto por
     clave): se registra `action=particiones_distintas` como aviso.
- **Hallazgos [medido] con aiokafka 0.15.0 y Kafka 4.1.2**:
  - Crear un topic que ya existe **no lanza excepción**: devuelve el error
    36 dentro de `topic_errors`. Hay que inspeccionar la respuesta, no esperar
    `TopicAlreadyExistsError`.
  - `alter_configs` (API legacy, no incremental) **funciona** en 4.1.2 y cambió
    `retention.ms` (comprobado con `kafka-configs.sh`). Al ser no incremental,
    sustituye todas las configuraciones dinámicas del topic por las enviadas:
    por eso se envían siempre las dos (`retention.ms` y `segment.ms`).
  - Un `describe_configs` inmediatamente posterior puede devolver el valor
    anterior (~1 s de desfase). No se verifica en el mismo instante; se
    comprueba en quickstart con `kafka-configs.sh`.
- **Por qué `segment.ms`**: Kafka solo borra segmentos **cerrados**. Con
  `segment.ms` por defecto (7 días) y retención de 7 días, un mensaje puede
  vivir hasta ~14 días. Acotar `segment.ms` a 1 día hace que la retención
  efectiva sea la configurada ±1 día. Coste: más ficheros de segmento (trivial
  a este volumen).
- **Alternativas descartadas**:
  - Fijar `KAFKA_LOG_RETENTION_MS` en el broker: la retención del topic ya
    creado no cambiaría (el override de topic manda) y afectaría a topics
    internos.
  - `retention.bytes` además de `retention.ms`: segunda variable sin necesidad;
    la spec exige «finita y configurable», y el tiempo basta.
  - `IncrementalAlterConfigs`: no está expuesto por aiokafka 0.15.0.

## R-06 · Nombres de esquemas y convención de nombres

- **Decisión**: esquemas `live`, `replay` e `ingesta`.
  - `live` y `replay` coinciden **literalmente** con los dos valores de `mode` del
    contrato (Constitución II) y con el vocabulario del enunciado: el consumidor
    obtiene el esquema destino directamente del `mode` validado (lista cerrada,
    compuesta con `sql.Identifier`), y el replay (004) reutiliza el mismo código
    cambiando solo de esquema (Constitución VI: «reutilizar el mismo
    procesamiento»).
  - `ingesta` es el espacio de ingesta/calidad (cuarentena, versión de esquema;
    en 002/003, extracciones y reglas). Está en español porque no corresponde a
    ningún valor del contrato.
- **Convención** (se aplica a mensaje, logs, BD y API):
  1. Campos que existen en el contrato del enunciado o en USGS conservan su
     nombre en inglés: `event_id`, `updated`, `source`, `mode`,
     `schema_version`, `ingested_at`, `processed_at`, `original`, `topic`.
  2. Conceptos propios del proyecto van en español: `versiones_evento`,
     `cuarentena`, `sintetico`, `motivo`, `detalle`, `recibido_en`,
     `particion`, `offset_kafka`, `version_esquema`.
  3. `partition` y `offset` son palabras reservadas o confusas en PostgreSQL;
     se usan `particion` y `offset_kafka`.
  4. Los valores de `result` en logs van en español (FR-027).
- **Alternativas descartadas**: todo en inglés (choca con las tablas que pide
  el alumno y con el idioma de la documentación); todo en español (obliga a
  traducir campos del contrato del enunciado y de USGS, con riesgo de confusión);
  un único esquema con columna `mode` (impide aislar replay por esquema, que es
  la opción que prefiere la Constitución VI).

## R-07 · Evolución del esquema sobre volúmenes existentes

- **Decisión (lo más simple defendible)**: tres piezas, sin herramienta externa.
  1. **Ficheros idempotentes** `db/init/NNN_nombre.sql`: todo con
     `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` / `ON CONFLICT DO NOTHING`.
     Sobre un volumen **vacío** los ejecuta `initdb` automáticamente (FR-009).
  2. **Tabla `ingesta.version_esquema`**: cada fichero termina insertando su
     propia fila (`version`, `nombre`). Deja constancia de qué se aplicó.
  3. **Guarda al conectar**: consumidor y API leen `max(version)` al abrir la
     conexión y exigen `>= ESQUEMA_VERSION_REQUERIDA` (constante en
     `common/db.py`, vale `1` en esta feature). Si falta o es menor, tratan la
     conexión como fallida (health no sano, `result=error reason=esquema_desactualizado`)
     y reintentan con backoff; en cuanto se aplica el esquema, se recuperan solos.
- **Aplicar a un volumen con datos** (cuando una feature futura cambie el
  esquema): una orden documentada que recorre los mismos ficheros dentro del
  contenedor:

  ```powershell
  docker compose exec postgres sh -c 'for f in /docker-entrypoint-initdb.d/*.sql; do psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB -f $f || exit 1; done'
  ```

  Es segura porque cada fichero es idempotente. El alumno nunca tiene que
  `down -v` para evolucionar el esquema.
- **Coste/riesgo**: depende de la disciplina de escribir SQL idempotente; no
  hay detección automática de ficheros modificados a posteriori (no hay checksum).
  Se acepta: el equipo es una persona y el conjunto de ficheros es pequeño.
- **Alternativas descartadas**:
  - Solo `initdb` + `down -v`: simple pero destruye los datos acumulados por
    002–004 (el histórico 2025 es costoso de recargar).
  - Alembic/Flyway/yoyo: herramienta nueva, directorio de versiones y comandos
    adicionales; desproporcionado para 3–5 ficheros (Constitución VIII).
  - Ejecutor de migraciones propio en Python al arrancar el consumidor: más
    código y concurrencia (bloqueo asesor) para un beneficio mínimo; además la
    Constitución pide `db/init/` como lugar del esquema inicial.
  - Que la API/consumidor creen tablas al arrancar (`CREATE TABLE IF NOT EXISTS`
    en Python): reparte el esquema entre código y SQL y rompe «versionado en
    `db/init/`».

## R-08 · PostgreSQL: imagen, healthcheck y contraseña

- **Decisión**: `postgres:17.11-alpine`, volumen `postgres_data` en
  `/var/lib/postgresql/data`, sin puerto publicado, contraseña con
  `${POSTGRES_PASSWORD:?…}`.
- **Motivo de 17 frente a 18**: PostgreSQL 18 de la imagen oficial cambia el
  `PGDATA` a un subdirectorio por versión (`/var/lib/postgresql/18/docker`) y
  recomienda montar en `/var/lib/postgresql`; montar en la ruta antigua es un
  error habitual. 17 conserva el punto de montaje clásico y es versión
  estable de largo recorrido. La etiqueta `17.11-alpine` fija versión menor
  (existe en Docker Hub el 2026-11-02).
- **Healthcheck**: `pg_isready -h 127.0.0.1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"`.
  **Importante**: durante `initdb` la imagen arranca un servidor temporal que
  escucha solo por socket Unix y después se reinicia. `pg_isready` sin `-h`
  usa el socket y declararía «sano» al servidor temporal, antes de que existan
  las tablas; con `-h 127.0.0.1` solo responde el servidor definitivo.
- **Contraseña**: `${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD en .env: copia .env.example a .env y define una contraseña}`
  falla con el nombre de la variable si falta **o está vacía** (la sintaxis `:?`
  cubre ambos casos), de modo que copiar `.env.example` sin editarlo también
  falla (spec, US1 escenario 4). Efecto aceptado: cualquier orden de `docker
  compose` (incluido `config`) necesita `.env`.
- **Alpine**: imagen pequeña; la ordenación por `locale` de musl no afecta a esta
  feature (claves `text` comparadas por igualdad). Si una feature futura
  ordenara texto por idioma, se revisará.
- **Alternativas descartadas**: `postgres:18` (punto de montaje, sin ventaja
  para este uso); `latest`/`17` sin versión menor (no reproducible); contraseña
  por defecto «postgres» (prohibido por spec y Constitución VII); publicar 5432
  «para depurar» (incumple FR-025; se usa `docker compose exec postgres psql`).

## R-09 · Cuarentena mínima

- **Decisión**: `ingesta.cuarentena` con `motivo`, `detalle`, `topic`,
  `particion`, `offset_kafka`, `clave bytea`, `original bytea`, `recibido_en`
  y `UNIQUE (topic, particion, offset_kafka)`.
- **Motivo**:
  - `bytea` es el único tipo que conserva **exactamente** lo que llegó
    («tal como llegó», FR-012): `text` rechaza UTF-8 inválido y el carácter
    `\x00`; `jsonb` rechazaría JSON ilegible por definición.
  - La clave se guarda aparte porque uno de los motivos es «clave distinta del
    `id`» y sin ella el caso no es reproducible.
  - `UNIQUE (topic, particion, offset_kafka)` + `ON CONFLICT DO NOTHING` hace
    idempotente la **reentrega** (el consumidor cae entre el commit de BD y el
    commit del offset).
- **Mensajes que el contrato da por válidos pero la BD rechaza** (por ejemplo
  un `\u0000` dentro de un string, que `jsonb` no admite, o un `CHECK` violado):
  son errores de **dato** (clase SQLSTATE 22/23), no de conexión. Si se
  reintentaran, bloquearían la partición para siempre. Regla: la transacción
  se revierte, se abre otra y el mensaje se guarda en cuarentena con
  `motivo=no_almacenable` y el `SQLSTATE` en `detalle`. Los errores de
  **conexión** (`OperationalError`, `InterfaceError`) nunca van a cuarentena:
  se reintenta el mismo mensaje sin confirmar offset.
- **Interpretación de FR-012 (confirmada, recogida en spec.md «Casos límite»)**:
  la idempotencia de la cuarentena es **por posición Kafka**. Una **reentrega** del
  mismo registro no duplica la entrada; un mensaje inválido **republicado**
  recibe otro offset y crea otra entrada (es otra ocurrencia). RK-04 resuelto.
- **Alternativas descartadas**: `text` para el original (pierde bytes);
  unicidad por hash del contenido (ocultaría ocurrencias repetidas y obliga a
  decidir qué hash); no persistir y solo registrar en log (incumple el cambio
  de FR-012 aprobado).

## R-10 · Contrato de mensaje v1 y su validación

- **Decisión**: mensaje JSON UTF-8; clave = `id` en UTF-8. Cuerpo:
  `schema_version` (entero `1`), `source`, `ingested_at` (UTC), `mode`
  (`live`/`replay`) y `event` (feature GeoJSON de USGS sin alterar).
  Detalle en [contracts/mensaje-kafka-v1.md](contracts/mensaje-kafka-v1.md).
- **Marca de sintético** (spec, Assumptions): se deduce de `source` con el
  prefijo reservado `synthetic-`; el `id` sintético usa el prefijo reservado
  `synthetic-` (el prefijo de la prueba de humo es `synthetic-smoke-`) y el
  `place` lleva «SINTÉTICO». No hay un booleano en el mensaje: un único campo
  que no puede contradecirse a sí mismo.
- **Coherencia obligatoria** (defensa en profundidad de la Constitución VI):
  `source` sintético ⇔ `id` sintético; si no, el mensaje se rechaza con
  `sintetico_inconsistente`. La base de datos repite la regla con un `CHECK`.
  Así un sintético no puede colarse en recuentos reales ni un evento real
  quedar etiquetado como sintético (y borrado por el procedimiento).
- **Validación a mano** (`common/contrato.py`), con motivos de lista cerrada:
  `valor_ausente`, `json_ilegible`, `no_es_objeto`, `campo_ausente`,
  `tipo_invalido`, `schema_version_no_soportada`, `source_invalido`,
  `mode_invalido`, `mode_no_corresponde_al_topic`, `ingested_at_invalido`,
  `evento_sin_id`, `clave_ausente`, `clave_distinta_de_id`, `updated_invalido`,
  `sintetico_inconsistente`. Más `no_almacenable` (R-09), que genera el consumidor
  al fallar la base. Reglas finas:
  - `json.loads` con `parse_constant` que rechaza `NaN`/`Infinity` (JSON no
    estándar que `jsonb` no admite).
  - `updated` debe ser **entero** (no `bool`, que en Python es subclase de `int`)
    en milisegundos desde epoch y dentro de un rango razonable
    (1970-01-01 … 2100-01-01). Se convierte con aritmética entera
    (`epoch + timedelta(milliseconds=…)`), sin pasar por `float`.
  - `ingested_at` debe ser ISO 8601 **con zona** y desplazamiento 0; el productor
    siempre escribe `…Z` con milisegundos.
  - Solo se valida lo imprescindible para identificar la versión
    (`event.id` y `event.properties.updated`). Coordenadas, tipo, magnitud
    y demás contenido USGS son de la feature 003 (spec, «Mensaje que no cumple el contrato»).
- **Extensibilidad sin romper v1**: nuevos valores de `source` (p. ej. el
  histórico) son compatibles; un campo obligatorio nuevo o un cambio de tipo
  exige `schema_version: 2`. El consumidor v1 rechaza `schema_version` ≠ 1 con
  motivo explícito, en vez de interpretar mal.
- **Alternativas descartadas**:
  - `pydantic` (modo estricto): ya está instalado por FastAPI y genera JSON
    Schema, pero hay que traducir sus errores a los motivos cerrados, su modo
    por defecto coacciona tipos (`"1"` → `1`) y hace menos visible qué se
    comprueba. Para una defensa oral pesa más una función corta y legible.
  - Librería `jsonschema`: dependencia nueva solo para validar; el JSON Schema
    de `contracts/` queda como **documentación** del contrato y se revisa con
    un test de ejemplo.
  - Un campo booleano `synthetic` en el mensaje: duplica la información de
    `source` y permite combinaciones contradictorias.
  - Avro/Protobuf + Schema Registry: servicio extra no exigido.

## R-11 · Mecanismo de la prueba de humo

- **Decisión**: módulo ejecutable `python -m observatorio.producer.smoke`, lanzado
  con `docker compose exec producer …`. Publica con un `AIOKafkaProducer`
  propio (`acks=all`, idempotente) y **solo tras `send_and_wait`** registra
  `result=publicado`; si no hay acuse, `result=error` y código de salida 1.
- **Determinismo**: por defecto el evento es **siempre el mismo**
  (`id = synthetic-smoke-0001`, `updated` fijo 1767225600000 = 2026-01-01T00:00:00Z).
  Así «volver a publicar» es un reenvío exacto de la misma versión
  (idempotencia comprobable), y tras borrar los sintéticos, publicar de nuevo
  lo recrea (spec, casos límite). Opciones:
  `--repeat N` (N publicaciones de la misma versión; SC-003 con N=5) y
  `--unico` (sufijo con la hora UTC, para crear otro evento sintético).
- **Evento**: feature GeoJSON de forma USGS con `source=synthetic-smoke`,
  `place="SINTÉTICO · prueba de humo (no es un terremoto real)"`, magnitud no
  nula y coordenadas válidas, para no depender de reglas de la 003.
- **Alternativas descartadas**:
  - Publicar automáticamente en cada arranque: contamina la base en cada
    `up` (la spec lo prohíbe).
  - Endpoint en la API: añadiría una ruta de administración (FR-024) y haría
    que la API escribiera en Kafka.
  - Servicio/perfil de Compose dedicado: sexto servicio o perfil extra.
  - `kafka-console-producer.sh` a mano: no garantiza el contrato ni el
    `send_and_wait` ni el log `clave=valor`. Sí se usa, a propósito, en las
    pruebas de mensajes **inválidos** (quickstart).
  - Script en el anfitrión: el host tiene Python 3.13 y no la imagen.
- **Eliminación de sintéticos**: `scripts/borrar_sinteticos.sql`
  (`DELETE FROM live.versiones_evento WHERE sintetico`, y solo eso) ejecutado
  con una orden documentada (quickstart y README). No toca Kafka ni la
  cuarentena. Los mensajes sintéticos permanecen en el topic hasta que vence la
  retención; no se vuelven a consumir salvo que se reinicie el grupo.

## R-12 · Salud de los servicios

- **Decisión**:
  - Productor y consumidor ejecutan un **servidor HTTP mínimo** sobre
    `asyncio.start_server` (≈ 30 líneas, sin dependencias) en `HEALTH_PORT`
    (8081), accesible solo desde la red de Docker del propio contenedor: **no
    se publica** (`ports` ausente; Constitución VII).
  - `GET /health` devuelve `200 {"status":"ok"}` si **todas** las comprobaciones
    registradas están en verde y `503 {"status":"unhealthy","failing":[…]}` si
    alguna falla. Comprobaciones: productor `kafka`; consumidor `kafka`,
    `postgres`, `catalogo`; API `postgres`.
  - El healthcheck de Compose ejecuta
    `python -m observatorio.common.healthcheck`, que hace un `GET` a
    `http://127.0.0.1:$HEALTH_PORT/health` con `urllib` (código de salida 0/1);
    la URL se deriva solo de `HEALTH_PORT` (no hay variable `HEALTH_URL`).
    Usa `127.0.0.1` **dentro del propio contenedor**; FR-006 prohíbe `localhost`
    para direcciones **entre servicios**.
  - **Sondas activas**: una tarea periódica (`HEALTH_PROBE_INTERVAL_SECONDS=5`)
    comprueba cada dependencia: PostgreSQL con `SELECT 1`; Kafka con una
    petición de metadatos (`producer.client.fetch_all_metadata()` /
    `consumer.topics()` bajo `asyncio.wait_for`). Sin sonda, un servicio
    inactivo no se enteraría de que perdió la conexión (el consumidor está
    bloqueado esperando mensajes). Detección en ≤ 5 s + 3 reintentos × 10 s de
    Compose = ≤ ~35 s, dentro del límite de 60 s (SC-006).
  - Estado «sano» solo cuando las conexiones están **establecidas**
    (FR-004): al arrancar, todas las comprobaciones empiezan en rojo.
  - La API sirve su propio `/health` en el puerto 8000 con
    `{"status":"ok"}` / `{"status":"unhealthy"}` **sin lista de componentes**
    (es público; FR-024) y la lista de fallos solo va a los logs.
- **Alternativas descartadas**:
  - `curl`/`wget` en el healthcheck: no están en `python:3.12-slim`; instalarlos
    añade capas y superficie.
  - Comprobar solo que el puerto TCP acepta conexiones: no refleja Kafka,
    PostgreSQL ni el catálogo (FR-004 lo exige).
  - Hilo con `http.server`: otro modelo de concurrencia y no detecta que el bucle
    de eventos esté bloqueado; con `asyncio` en el mismo bucle, si este se
    cuelga, la salud también falla.
  - Fichero «latido» en disco: sin puerto, pero no distingue estados parciales
    ni da cuerpo útil al diagnosticar.
  - Publicar los puertos de salud en el anfitrión: prohibido (VII, v2.0.1).
  - Kafka: se conserva el healthcheck existente
    (`kafka-broker-api-versions.sh --bootstrap-server localhost:9092`, que dentro del
    contenedor de Kafka apunta al propio Kafka).

## R-13 · Reintentos, supervisión y orden de arranque

- **Decisión**:
  - Función pura `esperas(inicial=1, factor=2, tope=30)` (1, 2, 4, 8, 16, 30, 30…)
    y `reintentar(operacion, …)` con `sleep` inyectable para probar sin esperar.
    Cada intento registra `result=reintento attempt=N wait_s=S dependency=…
    reason=…`. Sin jitter: hay un único cliente por dependencia, no hay
    estampida.
  - Cada servicio ejecuta un **supervisor**: abre la conexión con reintentos; si una
    sonda falla `PROBE_FALLOS_REINICIO` veces seguidas (3), cancela la sesión
    y la **recrea** con backoff. Cubre «tras perder la conexión» (FR-005) incluso
    si el cliente de aiokafka se quedara en un estado intermedio al reiniciarse el broker.
  - **Sin** `depends_on: condition: service_healthy` hacia Kafka/PostgreSQL. Si
    existiera, el orden lo resolvería Compose y el código de reintentos no
    se ejercitaría nunca en el arranque; además impediría el escenario «arrancar
    el consumidor con PostgreSQL detenido» (US3) con `up --no-deps`. La
    resiliencia vive **solo** en el código, que es lo que exige el enunciado
    («el orden de arranque por sí solo no garantiza…»).
  - `restart: unless-stopped` en los cinco servicios (recuperación tras reinicio del
    equipo). Ningún servicio sale por dependencia ausente, así que no habrá
    reinicios por error de conexión (SC-006).
- **Alternativas descartadas**: `depends_on: service_healthy` (arriba);
  `tenacity`/`backoff` (dependencia para 15 líneas, y queremos el log
  `attempt/wait_s` exacto); salir con error y dejar que Docker reinicie
  (incumple FR-005 y ensucia el estado); bucle `sleep` fijo (no es progresivo).

## R-14 · Logs `clave=valor`

- **Decisión**: un `logging.Formatter` propio
  (`ts=2026-11-02T12:00:00.123Z level=INFO service=consumer result=persistido event_id=… updated=… `)
  y funciones `registrar(logger, result=…, **campos)`. Reglas completas en
  [contracts/logs.md](contracts/logs.md).
  - Valores con espacios, `=`, comillas o saltos de línea se entrecomillan y se
    escapan; el *traceback* va en una sola línea (`exc="…\n…"` con `\n` literal).
  - Registros de librerías (aiokafka, psycopg, uvicorn) pasan por el mismo
    formateador y reciben `result=info` (o `result=error` si el nivel es ≥ ERROR),
    de modo que **el 100 % de las líneas** cumple `service` + `result` (SC-009).
  - **uvicorn** se lanza con `log_config=None` y `access_log=False`; la API
    registra su propio acceso (nivel DEBUG para `/health`, INFO para `/status`)
    en formato `clave=valor`. Sin esto, uvicorn imprimiría líneas
    `INFO:     172.18.0.1 - "GET /health…` que rompen SC-009.
  - **Secretos**: el formateador sustituye por `***` cualquier aparición de los
    valores secretos conocidos (`POSTGRES_PASSWORD`) y nunca se registra la
    configuración de conexión; `repr` de los ajustes oculta los secretos.
- **Resultado `published` frente a `publicado`**: la spec usa ambas grafías
  (US2 escenario 1 dice `result=published`; FR-027 y FR-012 usan «publicado» y
  `result=rechazado`) y la regla del repositorio da `result=published` como
  ejemplo. Se adopta el **español** para todo el conjunto cerrado
  (`publicado`, `persistido`, `omitido`, `rechazado`, `error` + `iniciado`,
  `listo`, `reintento`, `detenido`, `info`), por coherencia con FR-012/FR-027 y
  porque mezclar idiomas en un conjunto cerrado sería peor. Se pide al analista
  que unifique US2.1 (riesgo RK-05).
- **Alternativas descartadas**: `structlog`/`python-json-logger` (JSON, no
  `clave=valor`; dependencia nueva); `logging` por defecto con mensajes
  libres (no verificable con una expresión regular); un único campo `msg` con el
  texto (no filtrable por `event_id`).

## R-15 · Transacción, commit del offset e idempotencia

- **Decisión**: por cada registro, una transacción de PostgreSQL
  (`async with conn.transaction()`), y **solo después de salir de ella con éxito**,
  `await consumer.commit({tp: msg.offset + 1})` (el offset confirmado es el del
  *siguiente* mensaje, según la documentación de aiokafka). `enable_auto_commit=False`.
  - Válido → `INSERT … ON CONFLICT (event_id, updated) DO NOTHING`; `rowcount=1`
    → `persistido`; `rowcount=0` → `omitido`.
  - Inválido → `INSERT` en cuarentena `ON CONFLICT DO NOTHING` → `rechazado`.
  - Error de conexión → no se confirma, se reconecta con backoff y se **reintenta
    el mismo mensaje** (el consumidor no avanza). Mientras tanto aiokafka sigue
    enviando latidos; si la espera supera `max_poll_interval_ms` (5 min), el
    grupo reasigna la partición y el commit fallará con error de grupo: se
    registra `result=error` y el mensaje se reentrega y queda `omitido`
    (correcto por idempotencia).
  - Error de dato (SQLSTATE 22/23) → cuarentena `no_almacenable` (R-09).
  - Cualquier otra excepción → `result=error`, backoff y reintento (nunca se
    avanza el offset ni se descarta en silencio).
- **Commit por mensaje**: coste de una petición extra por mensaje; con unos
  pocos mensajes por segundo es irrelevante y mantiene el razonamiento «offset
  = último mensaje durable». Procesar en lotes es una optimización para 004
  (replay masivo), que debería medirse en el informe del apartado 10.
- **Ventana de fallo**: si el proceso cae tras el commit de BD y antes del
  commit del offset, el mensaje se reentrega y resulta `omitido` (SC-004).
- **Alternativas descartadas**: auto-commit (puede perder mensajes); commit
  antes de la escritura (at-most-once); transacciones Kafka *exactly-once*
  (complejidad que la idempotencia por clave única ya resuelve, Constitución III);
  `INSERT … ON CONFLICT DO UPDATE` (el historial no se sobrescribe).

## R-16 · Compose: una imagen, entorno explícito

- **Decisión**: ancla YAML `x-backend` con `build: ./backend` e
  `image: observatorio-backend:local` compartida por `producer`, `consumer` y
  `api`; cada uno solo cambia `command`. El resultado son tres contenedores de la
  **misma imagen** (comprobable por ID). Construir con `docker compose build`
  repetido reutiliza la caché de capas.
- **Entorno por servicio** con `environment:` explícito y `${VAR:-valor}`,
  **sin** `env_file: .env`: el productor no necesita ni debe recibir la contraseña
  de PostgreSQL (mínimo privilegio); Kafka nunca recibe variables de la
  aplicación.
- **Un solo contexto**: `backend/` (con `backend/.dockerignore`). El
  `.dockerignore` de la raíz no afecta a este contexto.
- **Usuario no root** en la imagen (`USER appuser`, UID 10001); el catálogo se
  monta `./catalogo:/catalogo:ro` y no se puede escribir (US5, escenario 4).
- **Alternativas descartadas**: tres `Dockerfile` o tres imágenes (viola FR-003);
  `image:` sin `build` en dos de ellos (rompe `docker compose build consumer`);
  `env_file` global (fuga de secretos entre servicios).

## R-17 · Estrategia de pruebas

- **Decisión**: `pytest` dentro de la imagen
  (`docker compose run --rm --no-deps consumer pytest -q`; el host tiene Python
  3.13, la imagen 3.12). Pruebas **sin infraestructura**: la lógica se escribe como
  funciones puras o con dependencias inyectadas (`sleep`, fábrica de
  conexión, reloj).
  - Cubiertos: contrato v1, backoff, formato de logs, validación del catálogo,
    decisión del consumidor (persistido/omitido/rechazado/no almacenable),
    clasificación de errores de BD, configuración, estado de salud, reglas de
    `ensure_topic` (qué cambiar), construcción del evento sintético y del
    estado de la API.
  - Las pruebas asíncronas se ejecutan con `asyncio.run(...)` dentro de funciones
    de prueba normales: no hace falta `pytest-asyncio`.
  - La API se prueba a nivel de **función pura** (`armar_estado`) y no con
    `TestClient`, que exige `httpx` (dependencia extra solo para pruebas).
  - Las pruebas contra la pila (humo, reenvío, reinicio, caída de PostgreSQL,
    persistencia) son pasos verificables en [quickstart.md](quickstart.md) para el
    `verifier`.
- **Fixtures del contrato**: `backend/tests/fixtures/mensaje_v1_ejemplo.json` es
  copia idéntica de `contracts/mensaje-kafka-v1.ejemplo.json` (la carpeta `specs/`
  no entra en la imagen). Quickstart incluye una comparación `Get-FileHash`.
- **Alternativas descartadas**: pruebas de integración con `testcontainers`
  (necesita el socket de Docker dentro del contenedor); mocks de aiokafka
  (acoplan la prueba a la implementación); ejecutar pytest en el host (versión
  distinta de Python).

## R-18 · Catálogo de países

- **Decisión**: el consumidor carga `catalogo/paises.geojson` (montado en
  `/catalogo`, solo lectura) al arrancar, **antes** de conectar con PostgreSQL o
  Kafka, con `json` + `shapely.geometry.shape`. Motivos de error de lista
  cerrada: `catalogo_ausente`, `catalogo_ilegible`, `catalogo_vacio`,
  `geometria_no_poligonal`, `adm0_a3_ausente`, `adm0_a3_repetido`.
  Log de éxito: `result=listo component=catalogo paises=242 fuente=/catalogo/paises.geojson`.
- **Si es inválido**: log `result=error motivo=…`, la comprobación `catalogo`
  queda en rojo, el consumidor **no consume** y permanece en ejecución
  (spec, Assumptions: no reintenta la lectura).
- **Geometrías inválidas topológicamente** (autointersección): no bloquean
  en esta feature; se cuentan y se registran (`geometrias_invalidas=N`; el
  manifiesto del catálogo entregado registra 0). Su tratamiento (reparación o
  exclusión) es una decisión de la 003, al construir el índice espacial.
- **No se guardan las geometrías** en memoria (no se asigna país en 001); la 003
  ampliará el cargador con el índice `STRtree`.
- **Alternativas descartadas**: validar con el script `descargar_paises.py`
  (descarga, no es el cargador de ejecución); no depender de Shapely
  (la spec/decisión previa exige validar con él, y 003 lo necesita);
  reintentar la lectura (es un fichero local; la corrección exige reiniciar).

## R-19 · Superficie de la API

- **Decisión**:
  - `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`: ni Swagger ni
    `openapi.json` públicos por el túnel. El contrato vive en
    `docs/CONTRATO-API.md` y en [contracts/api.openapi.yaml](contracts/api.openapi.yaml).
  - `/health` → 200/503 (para Compose y monitorización). `/status` → **siempre
    200** mientras la API viva: con la base caída informa
    `base_de_datos: "fallida"` y recuentos `null` («no disponible», nunca 0,
    FR-023), para que el panel muestre el estado en lugar de un error de red.
  - Consulta a BD con `asyncio.wait_for(…, 3 s)`; un fallo marca la conexión
    como perdida y dispara la reconexión con backoff en segundo plano.
  - «Eventos» = `count(DISTINCT event_id)` sobre `live.versiones_evento`
    (una versión es una fila; un evento puede tener varias). Cuesta O(n) por
    consulta (escaneo); aceptable ahora y sustituible en la 003 por el
    **estado actual**, que es de donde deben salir las agregaciones.
  - «Último evento procesado» = fila con mayor `processed_at` (índice descendente;
    O(log n)).
- **Alternativas descartadas**: dejar `/docs` (más superficie sin aportar al
  panel); `/status` con 503 cuando falla la BD (el panel perdería el detalle);
  contar con `count(*)` (contaría versiones, no eventos); caché de recuentos
  (estado oculto y posibles incoherencias).

## R-20 · Un único rol de base de datos

- **Decisión**: una sola cuenta (`POSTGRES_USER`) para consumidor y API en esta
  feature. Crear roles con privilegios distintos (`escritor`, `lector`) añade
  dos variables secretas y `GRANT` por esquema que aún no tienen tablas
  estables. **Riesgo anotado** (RK-06): la API tiene privilegios de escritura
  que no usa; se recomienda crear un rol de solo lectura en la feature 005, cuando
  se defina la superficie analítica.

## R-21 · Posición inicial del grupo de consumo

- **Decisión**: `auto_offset_reset="earliest"`, `group_id=CONSUMER_GROUP`.
  Con un grupo sin offsets confirmados, un mensaje publicado **antes** de que el
  consumidor arrancara por primera vez se lee igualmente (US2 escenario 3).
  Si los offsets del grupo caducan (retención de offsets del broker: 7 días por
  defecto), se relee desde el principio del topic: es seguro porque la escritura
  es idempotente (resultado `omitido`).
- **Alternativa descartada**: `latest` (perdería lo publicado con el consumidor parado).

## R-22 · Documentación operativa

- **Decisión**: apartado único «Puertos, listeners y arranque» en `README.md`
  (puertos publicados, listeners de Kafka, arranque/parada, reinicio sin
  pérdida, borrado con `down -v`, retención, prueba de humo, eliminación de
  sintéticos, resolución de conflicto de puertos, aplicar esquema a un volumen
  existente). Es el lugar que la spec asume y lo primero que ve quien clona.
- **Alternativa descartada**: `docs/OPERACION.md` separado (otro fichero que
  mantener sincronizado y que alguien tiene que encontrar).
- El `README.md` actual usa `cp .env.example .env` en un bloque `bash`:
  se sustituye por la orden de PowerShell (`Copy-Item`).

## R-23 · Ficheros de contexto de agente

Los scripts `setup-plan.ps1` y `setup-tasks.ps1` de este repositorio **no
actualizan** ningún `AGENTS.md`/`CLAUDE.md`/similar (solo copian la plantilla y
devuelven rutas). No se ha creado ni modificado ningún fichero de contexto de
agente. Único fichero creado fuera de `specs/001-esqueleto/`: `docs/CONTRATO-API.md`
(lo exige la Constitución II y el rol del arquitecto).

---

## Riesgos y puntos abiertos

| ID | Riesgo / duda | Mitigación o propuesta |
| --- | --- | --- |
| RK-01 | Comportamiento de aiokafka 0.15.0 al **reiniciar el broker con el cliente vivo** (reconexión del consumidor/grupo) | Supervisor con recreación de la sesión (R-13) + prueba de quickstart §3 (reiniciar `kafka`) |
| RK-02 | `describe_configs` justo tras `alter_configs` puede devolver el valor anterior | No se verifica en el acto; se comprueba con `kafka-configs.sh` |
| RK-03 | `python:3.12-slim` y dependencias transitivas flotan | Fijar tag de parche/digest y `pip freeze` como restricciones en 007 si hace falta |
| RK-04 | FR-012: ¿«reenviar el mismo mensaje rechazado» = reentrega o republicación? | **Resuelto**: idempotencia por posición Kafka (reentrega no duplica; republicación con otro offset crea otra entrada). Escrito en spec.md «Casos límite» |
| RK-05 | La spec mezclaba `result=published` y `result=rechazado` | Resuelto: español en todo; US2.1 y la regla del repositorio unificadas |
| RK-06 | API con rol de escritura sin usarlo | Rol de solo lectura en la 005 |
| RK-07 | El esquema evoluciona por SQL idempotente sin checksum | Disciplina + guarda de versión; revisar en la 003 |
| RK-08 | `${POSTGRES_PASSWORD:?}` hace que **toda** orden de Compose exija `.env` | Documentado en README y quickstart |
| RK-09 | Un mensaje con error no clasificado (excepción inesperada) se reintenta indefinidamente | Registro `result=error` con traza; es preferible a descartar en silencio (Constitución IV); revisar en 003 |

---

## Decisiones nuevas de implementación (001, tanda 1: Setup, Foundational y US1)

Registradas por `developer` al implementar T001–T029; no cambian ninguna decisión R-01…R-23.

| ID | Decisión | Motivo |
| --- | --- | --- |
| R-24 | `backend/Dockerfile` copia también `pytest.ini`, y este fija `cache_dir = /tmp/.pytest_cache` | Sin `pytest.ini` en `/app`, `pytest` no aplica `pythonpath = .` ni `testpaths` y no importa `observatorio`. `/app` es de root y el proceso corre como `appuser`: sin `cache_dir` en `/tmp`, pytest avisa `PytestCacheWarning` en cada ejecución |
| R-25 | `common/parada.py`: manejadores de `SIGTERM`/`SIGINT` en productor y consumidor (`evento_de_parada`, `hasta_parada`, `esperar`) | Python como PID 1 del contenedor ignora `SIGTERM` sin manejador; con él, `docker compose stop` de los tres servicios Python tarda ≈ 1,4 s en lugar de 10 s y registra `result=detenido`. También permite abandonar los reintentos de conexión al parar. uvicorn ya gestiona las señales en la API |
| R-26 | `config.cargar_o_salir()`: un `ConfigError` se registra como `result=error component=config reason=…` en formato `clave=valor` y el proceso sale con código 2 | El mensaje de `ConfigError` nombra la variable y nunca el valor; así el fallo de configuración también cumple SC-009 |
| R-27 | `api/estado.py::iso_utc` escribe siempre milisegundos (`2026-01-01T00:00:00.000Z`) | Es la convención de `docs/CONTRATO-API.md` («`2026-11-02T12:00:00.123Z`»); los ejemplos del contrato que muestran `updated` sin milisegundos (`…T00:00:00Z`) son equivalentes como `date-time`, pero el servicio no los reproduce literalmente. T054 debe alinear los ejemplos |
| R-28 | `armar_estado` con la base respondiendo y `conteos=None` devuelve `None` (no 0) | Regla del proyecto «los nulos no se rellenan con 0»; con tabla vacía `count()` devuelve 0 real y llega como tupla |
| R-29 | Sondas de PostgreSQL y Kafka en el consumidor (US1) solo **marcan** la salud; la reconexión y la recreación de la sesión llegan en US3 (T043–T046) | Respeta el orden de `tasks.md`; hasta entonces una caída en marcha deja el servicio `unhealthy` sin recuperación automática |
| R-30 | `reintentar()` usa `dependency=topic` (no `kafka`) para la espera del topic | Distingue en el log «el broker no responde» de «el topic aún no existe» (`reason=topic_no_existe`) |

Hallazgos de la validación de US1 que afectan a `quickstart.md` (corregir en la 001 por el arquitecto/verifier):

- §1.3: `\dt live.* ingesta.*` solo admite **un** patrón en `psql` (ignora el segundo y el tercero). Usar
  `SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('live','replay','ingesta') ORDER BY 1,2;`.
- §1.1: `docker ps` muestra `5432/tcp` para `postgres` (puerto **expuesto** por la imagen, no publicado en el anfitrión).
  El criterio SC-007 es «sin `127.0.0.1:…->`/`0.0.0.0:…->` salvo 8000 y 9092».
- §0: `Set-Content` en Windows PowerShell 5.1 escribe en la codificación ANSI; `.env.example` contiene tildes en los
  comentarios. Compose lo leyó bien, pero es más seguro escribir `.env` con `UTF8Encoding($false)`.
- `docker compose` (incluido `run` y `config`) exige `.env` con `POSTGRES_PASSWORD` por el `:?` (RK-08); los tests
  en la imagen con `docker compose run` también.