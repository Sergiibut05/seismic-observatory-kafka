# Contrato: mensaje Kafka v1

**Versión**: `schema_version = 1` | **Productores**: `producer` (002), replay (004), prueba de humo (001) | **Consumidor**: `consumer`
**Esquema**: [mensaje-kafka-v1.schema.json](mensaje-kafka-v1.schema.json) | **Ejemplo**: [mensaje-kafka-v1.ejemplo.json](mensaje-kafka-v1.ejemplo.json)
**Implementación compartida**: `backend/observatorio/common/contrato.py` (única fuente de verdad en ejecución; productor, consumidor y replay lo importan).

## Registro Kafka

| Parte | Valor |
| --- | --- |
| Topic | `eventos.live` en esta feature (variable `TOPIC_LIVE`); el replay usará otro topic (004) |
| Clave | `id` del evento original, UTF-8. Mismo `id` → misma partición → orden por evento |
| Valor | JSON UTF-8 (objeto) con los cinco campos siguientes |
| Cabeceras | ninguna |
| Acuse del productor | `acks=all`, idempotente; se considera publicado solo tras `send_and_wait` |

## Campos del valor

| Campo | Tipo | Obligatorio | Regla |
| --- | --- | --- | --- |
| `schema_version` | entero | sí | Exactamente `1`. Otro valor (o no entero, incluido `"1"` y `true`) → `schema_version_no_soportada` |
| `source` | texto | sí | `^[a-z][a-z0-9_-]{0,62}$`. Prefijo reservado `synthetic-` = sintético |
| `ingested_at` | texto | sí | ISO 8601 con zona y desplazamiento 0 (`…Z` o `…+00:00`), p. ej. `2026-11-02T12:00:00.123Z`. El productor siempre escribe `Z` con milisegundos |
| `mode` | texto | sí | `live` o `replay`, y **debe corresponder al topic** (`live` ↔ `TOPIC_LIVE`) |
| `event` | objeto | sí | Feature GeoJSON de USGS **sin alterar** |

Mínimo exigido dentro de `event` en la feature 001 (identificar la versión):

- `event.id`: texto no vacío, **igual a la clave del registro**.
- `event.properties.updated`: **entero** (no `bool`, no decimal), milisegundos desde epoch UTC,
  entre `0` y `4102444800000` (2100-01-01 UTC).

Todo lo demás (coordenadas, `type`, magnitud, profundidad…) lo valida la feature 003, que
amplía las reglas y la misma cuarentena, sin cambiar `schema_version`.

Cualquier campo adicional en la raíz del valor se **rechaza** (`additionalProperties: false`)
para que un cambio de contrato no pase inadvertido: añadir un campo exige decidir si es
compatible (nuevo valor opcional) y, si no, subir `schema_version`.

## Datos sintéticos

- `source` empieza por `synthetic-` (la prueba de humo usa `synthetic-smoke`).
- `event.id` empieza por `synthetic-` (la prueba de humo usa `synthetic-smoke-0001`, o
  `synthetic-smoke-<AAAAMMDDThhmmssZ>` con `--unico`).
- `event.properties.place` incluye «SINTÉTICO».
- **Coherencia**: `source` sintético ⇔ `id` sintético. Si no coinciden → `sintetico_inconsistente`.
- El consumidor guarda `sintetico = true` y la API los cuenta aparte; nunca entran en un
  recuento real (Constitución VI).

## Motivos de rechazo

Lista cerrada; se guardan en `ingesta.cuarentena.motivo` y en el log (`motivo=`). El campo
`detalle` nombra el campo concreto.

| `motivo` | Cuándo |
| --- | --- |
| `valor_ausente` | El registro no tiene valor (nulo) |
| `json_ilegible` | No es JSON UTF-8 válido, o contiene `NaN`/`Infinity` |
| `no_es_objeto` | El JSON es válido pero la raíz no es un objeto |
| `campo_ausente` | Falta `schema_version`, `source`, `ingested_at`, `mode` o `event`, o hay campos desconocidos en la raíz (el detalle lo indica) |
| `tipo_invalido` | Un campo tiene un tipo distinto del documentado (p. ej. `event` no es objeto) |
| `schema_version_no_soportada` | `schema_version` distinto de `1` |
| `source_invalido` | `source` no cumple el patrón |
| `mode_invalido` | `mode` no es `live` ni `replay` |
| `mode_no_corresponde_al_topic` | `mode` válido pero distinto del modo del topic (p. ej. `replay` en el topic live) |
| `ingested_at_invalido` | No es ISO 8601 con zona UTC |
| `evento_sin_id` | `event.id` ausente, no es texto o está vacío |
| `clave_ausente` | El registro no tiene clave |
| `clave_distinta_de_id` | La clave (UTF-8) no es igual a `event.id` (o no es UTF-8 válido) |
| `updated_invalido` | `event.properties.updated` ausente, no entero, `bool` o fuera de rango |
| `sintetico_inconsistente` | `source` sintético y `id` no sintético, o al revés |
| `no_almacenable` | Pasó la validación pero PostgreSQL lo rechazó por dato (SQLSTATE clase 22/23, p. ej. `\u0000` en un string). **Lo genera el consumidor**, no el validador |

Orden de comprobación (el **primer** fallo decide el motivo): valor → JSON → objeto →
campos de la raíz → `schema_version` → `source` → `mode` (valor) → `mode` frente al topic →
`ingested_at` → `event` → `event.id` → clave presente → clave = id → `updated` → coherencia
sintética.

## Reglas de compatibilidad (versionado)

| Cambio | ¿Compatible con v1? |
| --- | --- |
| Nuevo valor de `source` (p. ej. `usgs-historico`) | Sí |
| Nuevas propiedades dentro de `event` (USGS las añade) | Sí (se conservan sin alterar) |
| Campo nuevo en la raíz | **No** hasta que se documente: v1 lo rechaza → subir a v2 o ampliar v1 explícitamente |
| Cambiar tipo/semántica de un campo o hacerlo obligatorio | No → `schema_version: 2` |

Cuando exista v2, el consumidor aceptará ambas versiones durante la transición y la
documentación listará las dos.

## Ejemplo de registro inválido (para pruebas manuales)

| Entrada | Resultado esperado |
| --- | --- |
| clave `k`, valor `{no es json` | `rechazado motivo=json_ilegible` |
| clave `a`, valor `{"schema_version":1,…,"event":{"id":"b",…}}` | `rechazado motivo=clave_distinta_de_id` |
| `mode":"replay"` en el topic live | `rechazado motivo=mode_no_corresponde_al_topic` |
| `schema_version: 2` | `rechazado motivo=schema_version_no_soportada` |
