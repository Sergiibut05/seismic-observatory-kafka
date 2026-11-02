# Contrato de la API

> Estado: **feature 001-esqueleto** (solo salud y estado). Los endpoints analíticos,
> filtros y CORS para Netlify se añaden en la feature 005. El panel solo debe consumir
> campos definidos en este documento (Constitución II).
>
> Fuente máquina: [specs/001-esqueleto/contracts/api.openapi.yaml](../specs/001-esqueleto/contracts/api.openapi.yaml).
> La API **no** sirve `/docs`, `/redoc` ni `/openapi.json`.

## Convenciones

- Base: `http://127.0.0.1:8000` (publicado solo en el bucle local; HTTPS lo aporta ngrok).
- Formato: JSON UTF-8. Instantes en **UTC**, ISO 8601 con `Z` (`2026-11-02T12:00:00.123Z`).
- Sin autenticación (CORS no es autenticación; ver feature 005). Sin rutas de administración.
- Nombres de campo: los que vienen del contrato Kafka/USGS (`event_id`, `updated`, `source`,
  `processed_at`, `generated_at`) en inglés; los conceptos propios en español.
- Las respuestas no incluyen secretos, cadenas de conexión ni detalles de infraestructura.

## `GET /health`

Salud de la API. **200** solo si la API puede operar, incluida la conexión a PostgreSQL;
**503** en otro caso. El cuerpo no detalla el motivo (consulta los logs).

```json
{ "status": "ok" }
```

```json
{ "status": "unhealthy" }
```

## `GET /status`

Estado del sistema para el panel. **Siempre 200** mientras la API esté viva.

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `base_de_datos` | `"conectada"` \| `"fallida"` | Resultado de la última comprobación de la conexión a PostgreSQL |
| `eventos_reales` | entero \| `null` | Eventos distintos (`event_id`) **no** sintéticos. `null` = no disponible (la base no responde); nunca se informa como 0 |
| `eventos_sinteticos` | entero \| `null` | Eventos distintos sintéticos. `null` = no disponible |
| `ultimo_evento` | objeto \| `null` | Última versión procesada por el consumidor; `null` si no hay eventos o la base no responde |
| `ultimo_evento.event_id` | texto | Identificador del evento |
| `ultimo_evento.updated` | instante UTC | Versión del evento |
| `ultimo_evento.source` | texto | Origen (`usgs`, `synthetic-smoke`…) |
| `ultimo_evento.sintetico` | booleano | `true` si es un dato sintético |
| `ultimo_evento.processed_at` | instante UTC | Cuándo lo procesó el consumidor |
| `generated_at` | instante UTC | Cuándo se generó la respuesta |

Tras la prueba de humo:

```json
{
  "base_de_datos": "conectada",
  "eventos_reales": 0,
  "eventos_sinteticos": 1,
  "ultimo_evento": {
    "event_id": "synthetic-smoke-0001",
    "updated": "2026-01-01T00:00:00Z",
    "source": "synthetic-smoke",
    "sintetico": true,
    "processed_at": "2026-11-02T12:00:00.456Z"
  },
  "generated_at": "2026-11-02T12:00:05.000Z"
}
```

Con PostgreSQL caído:

```json
{
  "base_de_datos": "fallida",
  "eventos_reales": null,
  "eventos_sinteticos": null,
  "ultimo_evento": null,
  "generated_at": "2026-11-02T12:00:05.000Z"
}
```

Reglas: los recuentos son de **eventos**, no de versiones ni de mensajes; los sintéticos nunca
se suman a los reales; el panel debe mostrar «ND»/«no disponible» ante `null` (no un 0).

## Cambios

| Versión | Feature | Cambio |
| --- | --- | --- |
| 0.1.0 | 001-esqueleto | `GET /health`, `GET /status` |
