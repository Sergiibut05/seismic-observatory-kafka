# Modelo de datos: Esqueleto de extremo a extremo (001-esqueleto)

**Spec**: [spec.md](spec.md) | **Decisiones**: [research.md](research.md) (R-06, R-07, R-09)

Alcance: lo mínimo para la prueba de humo y la cuarentena. El modelo completo
de eventos (estado actual, historial, países, extracciones) es de la feature 003;
este modelo **no se sustituye, se amplía** (spec, Assumptions).

## 1. Modelo conceptual

```text
 Mensaje Kafka v1 ──(1 mensaje válido = 0..1 fila)──► Versión de evento recibida
        │                                                  (evento, versión)
        └─(1 mensaje inválido = 0..1 fila)────────────► Entrada de cuarentena
                                                          (posición Kafka)

 Esquema aplicado ── registra ──► Versión del esquema SQL
 Catálogo de países ── (solo se carga y valida; no se guarda en BD) ──
```

| Entidad | Grano | Identidad natural |
| --- | --- | --- |
| Versión de evento recibida | una versión (`event_id`, `updated`) de un evento | `(event_id, updated)` |
| Entrada de cuarentena | un registro Kafka que incumple el contrato o no es almacenable | `(topic, particion, offset_kafka)` |
| Versión del esquema SQL | un fichero `db/init/NNN_*.sql` aplicado | `version` |

Relaciones: no hay claves foráneas entre tablas (la cuarentena guarda **bytes**
de un mensaje que por definición no tiene un evento al que apuntar). El «evento»
como entidad con estado actual aparece en la 003; aquí «evento» = conjunto de
versiones con el mismo `event_id`.

### Regla de recuentos (spec FR-019, FR-023)

- «Eventos reales» = `count(DISTINCT event_id) FILTER (WHERE NOT sintetico)`.
- «Eventos sintéticos» = `count(DISTINCT event_id) FILTER (WHERE sintetico)`.
- Un sintético **nunca** entra en el primero (la marca se calcula en la escritura
  y la BD verifica su coherencia; ver `CHECK` más abajo).

## 2. Modelo lógico

### 2.1 `live.versiones_evento` (espacio live)

Grano: una fila por versión recibida de un evento; **no se sobrescribe**.

| Columna | Tipo lógico | Nulo | Origen | Notas |
| --- | --- | --- | --- | --- |
| `event_id` | texto | no | `event.id` = clave Kafka | no vacío |
| `updated` | instante UTC | no | `event.properties.updated` (ms epoch) | versión; **UTC**, ver §4 |
| `schema_version` | entero pequeño | no | mensaje | `1` en esta feature |
| `source` | texto | no | mensaje | `usgs`, `synthetic-smoke`… |
| `mode` | texto | no | mensaje | siempre `live` en esta tabla |
| `sintetico` | booleano | no | derivado de `source` | `source` empieza por `synthetic-` |
| `ingested_at` | instante UTC | no | mensaje | instante de **ingesta** (productor) |
| `processed_at` | instante UTC | no | reloj de la BD | instante de **procesamiento** (consumidor), distinto de `ingested_at` |
| `topic`, `particion`, `offset_kafka` | texto, entero, entero largo | no | registro Kafka | trazabilidad hacia el mensaje |
| `original` | JSON binario | no | mensaje completo | contenido del mensaje v1 tal como se validó |

Restricciones:

- **Clave primaria `(event_id, updated)`**: una versión existe como máximo una vez
  (FR-016). Es la restricción que convierte el reenvío en un no-op.
- `CHECK (event_id <> '')`.
- `CHECK (mode = 'live')`: esta tabla solo contiene datos live (aislamiento, VI).
- `CHECK (sintetico = (source LIKE 'synthetic-%') AND sintetico = (event_id LIKE 'synthetic-%'))`:
  la marca es coherente con `source` y con el `id`. Violación = error de dato
  (SQLSTATE 23514) → cuarentena `no_almacenable`.

Tiempo: se separan **tres** instantes — ocurrencia (en `original`, `properties.time`;
se promueve a columna en la 003), `updated` (versión USGS) e `ingested_at` /
`processed_at`. Nada se guarda como texto ni sin zona.

Sobre `original`: es `jsonb`, así que se conserva el contenido **semántico**
(claves, valores, números) pero no el orden de claves ni el espaciado. Los bytes
exactos del mensaje siguen en Kafka mientras dure la retención y, para
mensajes inválidos, en `ingesta.cuarentena.original`. La conservación del
GeoJSON crudo de cada extracción (Constitución IV) es de la 002.

### 2.2 `ingesta.cuarentena` (espacio de ingesta/calidad)

Grano: un registro Kafka rechazado (una ocurrencia).

| Columna | Tipo lógico | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | entero largo, identidad | no | clave sustituta |
| `motivo` | texto | no | código de lista cerrada ([contratos](contracts/mensaje-kafka-v1.md#motivos-de-rechazo)) |
| `detalle` | texto | sí | campo o excepción concreta (sin secretos) |
| `topic`, `particion`, `offset_kafka` | texto, entero, entero largo | no | posición en Kafka |
| `clave` | binario | sí | clave tal como llegó (puede faltar) |
| `original` | binario | sí | valor tal como llegó; `NULL` si el valor era nulo |
| `recibido_en` | instante UTC | no | reloj de la BD al guardar |

Restricciones: **`UNIQUE (topic, particion, offset_kafka)`**: la reentrega del
mismo registro no duplica la entrada (FR-012; idempotencia por posición Kafka, ver spec «Casos límite» y R-09; una republicación con otro offset es otra entrada).

### 2.3 `ingesta.version_esquema`

| Columna | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `version` | entero | no | PK, `> 0` |
| `nombre` | texto | no | p. ej. `esquema_base` |
| `aplicada_en` | instante UTC | no | por defecto, reloj de la BD |

Fila inicial: `(1, 'esquema_base')`. Consumidor y API exigen `max(version) >= 1`.

### 2.4 Esquema `replay`

Se crea **vacío** (con `COMMENT ON SCHEMA`). Sus tablas las define la 004; mientras
tanto un mensaje `mode=replay` en el topic live se rechaza
(`mode_no_corresponde_al_topic`) y nada escribe aquí.

## 3. Modelo físico (referencia para `db/init/001_esquema_base.sql`)

El fichero real lo escribe `developer`; esto fija nombres, tipos e índices.

```sql
CREATE SCHEMA IF NOT EXISTS live;
CREATE SCHEMA IF NOT EXISTS replay;
CREATE SCHEMA IF NOT EXISTS ingesta;
COMMENT ON SCHEMA live    IS 'Datos del modo live (mode = live)';
COMMENT ON SCHEMA replay  IS 'Reservado para la reproducción histórica (feature 004)';
COMMENT ON SCHEMA ingesta IS 'Ingesta y calidad: cuarentena y versión del esquema';

CREATE TABLE IF NOT EXISTS ingesta.version_esquema (
    version      integer      PRIMARY KEY CHECK (version > 0),
    nombre       text         NOT NULL,
    aplicada_en  timestamptz  NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS live.versiones_evento (
    event_id        text         NOT NULL CHECK (event_id <> ''),
    updated         timestamptz  NOT NULL,
    schema_version  smallint     NOT NULL,
    source          text         NOT NULL,
    mode            text         NOT NULL DEFAULT 'live' CHECK (mode = 'live'),
    sintetico       boolean      NOT NULL,
    ingested_at     timestamptz  NOT NULL,
    processed_at    timestamptz  NOT NULL DEFAULT clock_timestamp(),
    topic           text         NOT NULL,
    particion       integer      NOT NULL,
    offset_kafka    bigint       NOT NULL,
    original        jsonb        NOT NULL,
    CONSTRAINT versiones_evento_pk PRIMARY KEY (event_id, updated),
    CONSTRAINT versiones_evento_sintetico_coherente CHECK (
        sintetico = (source   LIKE 'synthetic-%')
        AND sintetico = (event_id LIKE 'synthetic-%'))
);
CREATE INDEX IF NOT EXISTS versiones_evento_processed_at_idx
    ON live.versiones_evento (processed_at DESC);

CREATE TABLE IF NOT EXISTS ingesta.cuarentena (
    id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    motivo        text         NOT NULL,
    detalle       text,
    topic         text         NOT NULL,
    particion     integer      NOT NULL,
    offset_kafka  bigint       NOT NULL,
    clave         bytea,
    original      bytea,
    recibido_en   timestamptz  NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT cuarentena_posicion_uk UNIQUE (topic, particion, offset_kafka)
);

INSERT INTO ingesta.version_esquema (version, nombre)
VALUES (1, 'esquema_base') ON CONFLICT (version) DO NOTHING;
```

Decisiones de tipo: `timestamptz` (todo en UTC; el servidor y la sesión usan UTC,
y la aplicación siempre envía instantes con zona); `text` en lugar de
`varchar(n)` (en PostgreSQL no es más rápido y evita límites arbitrarios);
`GENERATED ALWAYS AS IDENTITY` en lugar de `serial` (estándar SQL, la secuencia
queda ligada a la columna); `clock_timestamp()` frente a `now()` para que
`processed_at`/`recibido_en` reflejen el instante real de la fila y no el inicio
de la transacción.

## 4. Conversión de tiempos

`updated` llega como entero de milisegundos desde epoch (USGS). El consumidor lo
convierte con `datetime(1970,1,1,tzinfo=UTC) + timedelta(milliseconds=ms)`
(aritmética entera, sin `float`) y lo envía como `timestamptz`. El log y el
mensaje conservan el entero original (identidad estable de la versión); la API
lo devuelve en ISO 8601 UTC con `Z`.

## 5. Índices: qué acelera cada uno y su coste

| Índice | Tabla | Consulta que acelera | Coste |
| --- | --- | --- | --- |
| `versiones_evento_pk` (B-tree único `(event_id, updated)`) | `live.versiones_evento` | (a) comprobación de duplicado de `ON CONFLICT` en cada escritura; (b) búsqueda de todas las versiones de un `event_id` (prefijo de la clave); (c) garantía de unicidad (FR-016) | Una inserción en B-tree por fila: O(log n); espacio ≈ tamaño de la clave. Imprescindible: sin él la idempotencia no existe |
| `versiones_evento_processed_at_idx` (B-tree `processed_at DESC`) | `live.versiones_evento` | «Último evento procesado» de `/status` (`ORDER BY processed_at DESC LIMIT 1`) en O(log n) en lugar de ordenar toda la tabla | Una inserción más por fila; como `processed_at` crece de forma monótona, las inserciones caen siempre en la hoja más reciente (coste bajo). Se consulta cada 60 s por el panel |
| `cuarentena_posicion_uk` (B-tree único `(topic, particion, offset_kafka)`) | `ingesta.cuarentena` | Idempotencia de la reentrega de un registro rechazado | O(log n) por rechazo; los rechazos son raros |
| `version_esquema_pkey` / `cuarentena_pkey` | `ingesta.*` | Claves primarias (identidad de fila) | Implícitos; tablas minúsculas |

**Índice considerado y rechazado**: índice parcial `WHERE sintetico` (acelera
`DELETE … WHERE sintetico` y el recuento sintético). Con las cantidades de esta
feature (≈ unidades de filas sintéticas) un recorrido secuencial es inmediato y el
índice solo añadiría escritura. Se reevaluará si la 007 replica datos
sintéticos para pruebas de escala.

## 6. Complejidad de las operaciones clave (insumo del apartado 10)

| Operación | Estructura | Caso medio | Peor caso | Nota |
| --- | --- | --- | --- | --- |
| Comprobar si una versión ya existe / insertar | B-tree PK | O(log n) | O(log n) | n = filas de `versiones_evento`; B-tree equilibrado |
| Listar versiones de un evento | prefijo del PK | O(log n + k) | O(log n + k) | k = versiones del evento |
| Último evento procesado | índice `processed_at DESC` | O(log n) | O(log n) | sin índice: O(n) |
| Recuento de eventos reales/sintéticos | escaneo + agregación `DISTINCT` | O(n) | O(n log n) si ordena | candidato a sustituirse por el estado actual en la 003 |
| Validación de un mensaje | análisis JSON + comprobaciones | O(m) | O(m) | m = bytes del mensaje |
| Carga/validación del catálogo | recorrido de entidades y vértices | O(V) | O(V) | V = vértices totales; `ADM0_A3` único con `set`: O(P) medio, O(P²) teórico por colisiones de hash |
| Backoff | secuencia `min(inicial·2^k, tope)` | O(1) por intento | O(1) | tope 30 s |

## 7. Ciclo de vida de un registro Kafka (transiciones)

```text
registro Kafka ─► validar_mensaje()
   ├─ válido ───────► transacción: INSERT versiones_evento ON CONFLICT DO NOTHING
   │                     ├─ rowcount=1 ─► persistido ─┐
   │                     ├─ rowcount=0 ─► omitido ────┤
   │                     ├─ error de dato (22/23) ─► (otra transacción) cuarentena no_almacenable ─► rechazado ─┤
   │                     └─ error de conexión ─► NO commit de offset ─► backoff ─► mismo registro
   └─ inválido ─────► transacción: INSERT cuarentena ON CONFLICT DO NOTHING ─► rechazado ─┤
                                                                                         ▼
                                                                       commit del offset (offset + 1)
```

El offset se confirma **solo** en las salidas que llegan a la caja final, y
siempre después del `COMMIT` de PostgreSQL.

## 8. Procedimiento de eliminación de sintéticos

`scripts/borrar_sinteticos.sql` (idempotente, una transacción):

```sql
BEGIN;
DELETE FROM live.versiones_evento WHERE sintetico;
COMMIT;
```

Solo elimina filas con `sintetico = true` (coherente con `source`/`id`
sintéticos por el `CHECK`), por lo que **no puede afectar a datos reales**. En
la 004 se ampliará a `replay`. Orden de ejecución documentada en
[quickstart.md](quickstart.md#2-prueba-de-humo-us2).
