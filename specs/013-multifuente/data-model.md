# Modelo de datos 013

Migración idempotente `db/init/006_multifuente.sql`. Los volúmenes existentes la reciben del
consumidor (`asegurar_modelo`), de los productores (`asegurar_tablas`) y de la fusión
(`asegurar_fusion`), como en features anteriores; `db/init/` solo se ejecuta en un volumen vacío.

## Ingesta (productores)

| Tabla | Cambio | Motivo |
|---|---|---|
| `ingesta.publicadas` | + `fuente text NOT NULL DEFAULT 'usgs'`; PK pasa de `(event_id, updated_ms)` a `(fuente, event_id, updated_ms)` | Los ids de USGS y EMSC son espacios distintos. Las filas existentes son de USGS. |
| `ingesta.consultas` | + `fuente text NOT NULL DEFAULT 'usgs'` | Saber de qué fuente es cada consulta (estado por fuente). |
| `ingesta.exclusiones` | + `fuente text NOT NULL DEFAULT 'usgs'` | Ídem para los excluidos. |

Consulta del productor: `SELECT event_id, updated_ms FROM ingesta.publicadas WHERE fuente = %s AND event_id = ANY(%s)` — solo los ids de la respuesta, no toda la tabla (con el relleno serán ~200.000 filas).

## Fusión (esquema `fusion`, lo escribe solo el servicio de fusión)

### `fusion.informe` — un informe de una fuente, en su última versión vista

| Columna | Tipo | Nota |
|---|---|---|
| `fuente` | text | `usgs` \| `emsc` |
| `id_origen` | text | id en la fuente |
| `updated_ms` | bigint | versión en la fuente (USGS `updated`; EMSC `lastupdate`) |
| `tiempo_ms` | bigint | hora de ocurrencia, ms UTC |
| `latitud`, `longitud` | double precision | |
| `profundidad` | double precision NULL | km, positiva hacia abajo |
| `magnitud` | double precision NULL | |
| `tipo_magnitud`, `lugar` | text NULL | |
| `ingested_at` | timestamptz | del mensaje de la fuente |
| `original` | jsonb | evento tal cual lo dio la fuente |
| `canonico` | text | evento fusionado al que pertenece |

- PK `(fuente, id_origen)`. Índices: `(tiempo_ms)` para buscar candidatos por ventana; `(canonico)` para reconstruir un evento.
- Grano: un informe por fuente e id; una revisión lo sustituye (el historial completo está en `live.versiones_evento`, dentro del mensaje v2).

### `fusion.canonico` — lo último emitido de cada evento fusionado

| Columna | Tipo | Nota |
|---|---|---|
| `id` | text PK | id canónico |
| `updated_ms` | bigint | versión emitida |
| `firma` | text | `fuente:id:updated` de sus informes, ordenados; si no cambia, no se emite |
| `fuente_principal` | text | |
| `actualizado_en` | timestamptz | auditoría |

### `fusion.descartes` — informes que la fusión no puede tratar

`id` identidad, `fuente`, `id_origen` (NULL si no se pudo leer), `motivo` (lista cerrada), `detalle`, `topic`, `particion`, `offset_kafka`, `visto_en`. Única por `(topic, particion, offset_kafka)`: una reentrega no duplica.

### Siembra (FR-009)

Al arrancar, `asegurar_fusion` copia a `fusion.informe` y `fusion.canonico` los eventos reales de `live.evento_actual` que aún no estén (`ON CONFLICT DO NOTHING`), con `fuente = 'usgs'`, `canonico = event_id` y el original de su versión vigente en `live.versiones_evento`. Así su pareja de EMSC se une a ellos en vez de duplicarlos.

## Analítico (lo escribe el consumidor)

| Tabla | Cambio |
|---|---|
| `live.versiones_evento`, `replay.versiones_evento` | + `fuentes text[]` (NULL en filas antiguas) |
| `live.evento_actual`, `replay.evento_actual` | + `fuentes text[] NOT NULL DEFAULT '{}'`; las filas existentes se rellenan con `ARRAY[source]` |

- `source` sigue siendo una sola fuente: la principal del evento (v2) o la del mensaje (v1).
- `fuentes` va ordenado alfabéticamente (`{emsc,usgs}`), para que dos versiones iguales lo sean también en la columna.
- `processed_at`, país, `sintetico` y las restricciones existentes no cambian.
