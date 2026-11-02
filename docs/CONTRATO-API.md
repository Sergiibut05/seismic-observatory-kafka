# Contrato de la API

> Versión **0.2.0** (feature 005-api; cambio **aditivo** sobre la 0.1.0 de 001-esqueleto). El panel
> solo debe consumir campos definidos en este documento (Constitución II).
>
> Fuente máquina: [specs/001-esqueleto/contracts/api.openapi.yaml](../specs/001-esqueleto/contracts/api.openapi.yaml).
> La API **no** sirve `/docs`, `/redoc` ni `/openapi.json`.

## Convenciones

- Base: `http://127.0.0.1:8000` (publicado solo en el bucle local; HTTPS lo aporta ngrok).
- Formato: JSON UTF-8. Instantes en **UTC**, ISO 8601 con `Z` y **siempre con milisegundos** (`2026-11-02T12:00:00.123Z`; un instante redondo se escribe `2026-01-01T00:00:00.000Z`).
- Solo `GET` (y `OPTIONS` para CORS). Cualquier otro método da **405**. Sin autenticación (CORS no es autenticación) y sin rutas de administración.
- Nombres de campo: los que vienen del contrato Kafka/USGS (`event_id`, `updated`, `source`,
  `processed_at`, `generated_at`) en inglés; los conceptos propios en español.
- Las respuestas no incluyen secretos, cadenas de conexión ni detalles de infraestructura.
- **Nulo ≠ 0**: un dato que no se conoce (magnitud sin informar, base caída, histórico sin cargar) es `null`, nunca `0`.
- Toda cifra sale del **estado actual** (una fila por `event_id`, la versión con `updated` más reciente), nunca de contar mensajes. Los eventos sin país se cuentan como «Sin país asignado».

## CORS

Origen exacto de Netlify (variable `CORS_ORIGEN_NETLIFY`, sin valor por defecto) y `http://localhost:4200`. Métodos `GET` y `OPTIONS`; cabecera permitida `ngrok-skip-browser-warning` (más las simples `Accept`, `Content-Type`…). Sin comodín (`*`) ni credenciales; el preflight se cachea 600 s. Un origen no autorizado no recibe ninguna cabecera `Access-Control-*`. Si la variable está vacía, solo `http://localhost:4200`.

## Filtros comunes

Parámetros de consulta, los mismos en `/eventos`, `/eventos/mapa`, `/recuentos/*` y `/distribuciones/*`. Un parámetro **desconocido o repetido** es 400, igual que un valor mal formado.

| Parámetro | Regla |
| --- | --- |
| `desde`, `hasta` | ISO 8601 **con zona** (`Z` u offset; un `+` se escribe `%2B`). Sin zona = 400. Se pasan a UTC. `desde` inclusivo, `hasta` exclusivo, `desde < hasta`. Se aplican sobre `ocurrencia` |
| `magnitud_min`, `magnitud_max` | Número finito entre −10 y 10, sin notación científica; `min ≤ max`. Con filtro, la magnitud nula **queda fuera**; sin él, entra |
| `pais` | Código `ADM0_A3` (tres mayúsculas, `USA`) o `Sin país asignado` (eventos sin polígono) |
| `subregion` | Texto de hasta 80 caracteres, igualdad exacta con la subregión del catálogo; `Sin país asignado` = eventos sin país. Con `pais`, se combinan con Y |
| `incluir_sinteticos` | `true` o `false` (defecto `false`). Los sintéticos llevan `sintetico: true`. La API nunca lee datos de reproducción |

`/comparacion-historica` solo admite `magnitud_min`, `magnitud_max`, `pais` y `subregion`.

## Errores

Cuerpo genérico, sin SQL, rutas, trazas ni el valor recibido.

| Estado | Cuerpo | Cuándo |
| --- | --- | --- |
| 400 | `{"error":"parametro_invalido","parametro":"magnitud_min"}` | Valor mal formado, parámetro desconocido o repetido |
| 503 | `{"error":"servicio_no_disponible"}` | PostgreSQL no responde o se agota el tiempo (5 s). **Nunca** una lista vacía ni ceros |
| 500 | `{"error":"error_interno"}` | Fallo no previsto |
| 404 / 405 | — | Ruta inexistente (`/docs`…) / método distinto de `GET` y `OPTIONS` |

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
| `ultima_ingesta_correcta` | instante UTC \| `null` | **0.2.0.** Fin de la última consulta al feed de USGS con HTTP 200 y sin error. `null` si aún no hubo ninguna o la base no responde |
| `periodo_consultado` | objeto \| `null` | **0.2.0.** `{desde, hasta}`: primera y última `ocurrencia` de los eventos **reales** del estado actual. `null` sin eventos reales o con la base caída |
| `datos_desactualizados` | booleano \| `null` | **0.2.0.** `true` si no hay ingesta correcta o la última supera el umbral; `false` si es reciente; `null` con la base caída |
| `umbral_datos_desactualizados_segundos` | entero | **0.2.0.** Umbral configurado (`DATOS_DESACTUALIZADOS_SEGUNDOS`, defecto 300, mínimo 60). Se informa siempre |
| `generated_at` | instante UTC | Cuándo se generó la respuesta |

```json
{
  "base_de_datos": "conectada",
  "eventos_reales": 254,
  "eventos_sinteticos": 2,
  "ultimo_evento": {
    "event_id": "mb90211798",
    "updated": "2026-11-02T15:59:20.370Z",
    "source": "usgs",
    "sintetico": false,
    "processed_at": "2026-11-02T16:00:27.936Z"
  },
  "ultima_ingesta_correcta": "2026-11-02T16:03:28.431Z",
  "periodo_consultado": { "desde": "2026-11-01T15:04:56.675Z", "hasta": "2026-11-02T15:47:36.330Z" },
  "datos_desactualizados": false,
  "umbral_datos_desactualizados_segundos": 300,
  "generated_at": "2026-11-02T16:03:31.832Z"
}
```

Con PostgreSQL caído (los datos de la base, `null`; el umbral es configuración y se informa):

```json
{
  "base_de_datos": "fallida",
  "eventos_reales": null,
  "eventos_sinteticos": null,
  "ultimo_evento": null,
  "ultima_ingesta_correcta": null,
  "periodo_consultado": null,
  "datos_desactualizados": null,
  "umbral_datos_desactualizados_segundos": 300,
  "generated_at": "2026-11-02T12:00:05.000Z"
}
```

Reglas: los recuentos son de **eventos**, no de versiones ni de mensajes; los sintéticos nunca se
suman a los reales; el panel debe mostrar «ND»/«no disponible» ante `null` (no un 0).

## `GET /eventos`

Lista paginada (tabla alternativa al mapa). Filtros comunes más `limite` (1–500, defecto 100) y `desplazamiento` (0–100.000, defecto 0). Orden: `ocurrencia` descendente y `event_id` ascendente.

```json
{
  "eventos": [
    {
      "event_id": "hv75067836",
      "ocurrencia": "2026-11-02T15:41:58.430Z",
      "updated": "2026-11-02T15:45:31.280Z",
      "magnitud": 2.1,
      "profundidad": 30.52,
      "longitud": -155.461,
      "latitud": 19.1575,
      "pais_codigo": null,
      "pais_nombre": "Sin país asignado",
      "subregion": null,
      "sintetico": false
    }
  ],
  "total": 254,
  "limite": 100,
  "desplazamiento": 0
}
```

`total` es el de eventos que cumplen los filtros, no el de la página. `magnitud` y `profundidad` pueden ser `null` (sin valor); la profundidad en km puede ser negativa. `pais_codigo` y `subregion` son `null` para «Sin país asignado».

## `GET /eventos/mapa`

GeoJSON `FeatureCollection` listo para `L.geoJSON`. Mismos filtros, sin paginar, con los **más recientes** hasta un tope fijo de 5000. Coordenadas `[longitud, latitud]`; la profundidad va en `properties`.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [-155.461, 19.1575] },
      "properties": {
        "event_id": "hv75067836",
        "ocurrencia": "2026-11-02T15:41:58.430Z",
        "updated": "2026-11-02T15:45:31.280Z",
        "magnitud": 2.1,
        "profundidad": 30.52,
        "pais_nombre": "Sin país asignado",
        "sintetico": false
      }
    }
  ],
  "total": 254,
  "devueltos": 1,
  "limite": 5000,
  "truncado": false,
  "generated_at": "2026-11-02T16:03:32.143Z"
}
```

Si hay más eventos que el tope, `truncado` es `true` y `total` es el total **real**; el panel debe avisarlo, nunca mostrar un corte silencioso.

## `GET /recuentos/pais` y `GET /recuentos/subregion`

Filtros comunes. «Sin país asignado» es una categoría más (en país con `codigo: null`; en subregión, los eventos sin país no tienen subregión y van con ese nombre). Orden por recuento descendente. La suma de las categorías es `total` y coincide con el `total` de `/eventos` con los mismos filtros.

```json
{
  "total": 254,
  "categorias": [
    { "codigo": "USA", "nombre": "Estados Unidos", "recuento": 197 },
    { "codigo": null, "nombre": "Sin país asignado", "recuento": 48 }
  ]
}
```

```json
{
  "total": 254,
  "categorias": [
    { "nombre": "Northern America", "recuento": 198 },
    { "nombre": "Sin país asignado", "recuento": 48 }
  ]
}
```

## `GET /recuentos/hora`

Una ventana por cada hora UTC de `[desde, hasta)`, **incluidas las horas con 0 eventos**. Sin `desde` ni `hasta`: últimas 24 h; solo `desde` llega hasta ahora; solo `hasta` retrocede 24 h. Máximo 31 días (400 si se excede). La primera y la última ventana pueden ser parciales si `desde`/`hasta` no son horas en punto. Un evento a las 10:59:59.999Z y otro a las 11:00:00.000Z caen en ventanas distintas.

```json
{
  "desde": "2026-11-02T06:00:00.000Z",
  "hasta": "2026-11-02T09:00:00.000Z",
  "total": 3,
  "ventanas": [
    { "inicio": "2026-11-02T06:00:00.000Z", "recuento": 0 },
    { "inicio": "2026-11-02T07:00:00.000Z", "recuento": 2 },
    { "inicio": "2026-11-02T08:00:00.000Z", "recuento": 1 }
  ]
}
```

## `GET /distribuciones/magnitud` y `GET /distribuciones/profundidad`

Filtros comunes. Intervalos fijos `[desde, hasta)` con extremos abiertos (`desde`/`hasta` `null`), todos presentes aunque tengan 0:

- magnitud: `< 0`, `0–1`, `1–2`, …, `8–9`, `≥ 9`.
- profundidad (`unidad: "km"`): `< 0`, `0–10`, `10–30`, `30–70`, `70–150`, `150–300`, `300–500`, `500–700`, `≥ 700`.

Un valor nulo **no cae en ningún intervalo ni se cuenta como 0**: va a `sin_valor`. `total` = intervalos + `sin_valor`.

```json
{
  "unidad": "magnitud",
  "total": 254,
  "sin_valor": 0,
  "intervalos": [
    { "desde": null, "hasta": 0, "etiqueta": "< 0", "recuento": 1 },
    { "desde": 0, "hasta": 1, "etiqueta": "0–1", "recuento": 46 }
  ]
}
```

## `GET /comparacion-historica`

Eventos reales de las **últimas 24 h** frente a la **media diaria de 2025**. Solo `magnitud_min`, `magnitud_max`, `pais` y `subregion` (el resto, 400). Magnitud mínima efectiva = máx(4, `magnitud_min`), declarada en `filtros_efectivos`. Denominador: 365 días, incluidos los de cero eventos. El histórico sale de una tabla propia (18.302 eventos de 2025), no del estado actual.

| Campo | Descripción |
| --- | --- |
| `ventana_actual` | `{desde, hasta, eventos}`: 24 h hasta `generated_at` |
| `historico_2025.estado` | `cargado` o `no_cargado` |
| `historico_2025.eventos` / `media_diaria` | Eventos de 2025 con los mismos filtros y `eventos / 365`. **0** con un país sin eventos en 2025; `null` si no está cargado |
| `cociente` | `ventana_actual.eventos / media_diaria`; `null` si la media es 0 o no está cargado |
| `filtros_efectivos` | `magnitud_min` (efectiva), `magnitud_max`, `pais`, `subregion` |
| `aviso` | Siempre presente: el último periodo puede estar incompleto por retrasos y revisiones de USGS |

```json
{
  "ventana_actual": { "desde": "2026-11-01T16:03:32.143Z", "hasta": "2026-11-02T16:03:32.143Z", "eventos": 30 },
  "historico_2025": { "estado": "cargado", "eventos": 18302, "dias": 365, "media_diaria": 50.1425 },
  "cociente": 0.6,
  "filtros_efectivos": { "magnitud_min": 4.0, "magnitud_max": null, "pais": null, "subregion": null },
  "aviso": "El último periodo puede estar incompleto: USGS publica con retraso y revisa los eventos después.",
  "generated_at": "2026-11-02T16:03:32.143Z"
}
```

Con el histórico sin cargar (200, nunca un 0 inventado; el panel muestra «no disponible»):

```json
{
  "ventana_actual": { "desde": "2026-11-01T16:04:51.483Z", "hasta": "2026-11-02T16:04:51.483Z", "eventos": 0 },
  "historico_2025": { "estado": "no_cargado", "eventos": null, "dias": 365, "media_diaria": null },
  "cociente": null,
  "filtros_efectivos": { "magnitud_min": 4.0, "magnitud_max": null, "pais": null, "subregion": null },
  "aviso": "El último periodo puede estar incompleto: USGS publica con retraso y revisa los eventos después. El histórico de 2025 no está cargado: no hay media ni cociente.",
  "generated_at": "2026-11-02T16:04:51.483Z"
}
```

## Cambios

| Versión | Feature | Cambio |
| --- | --- | --- |
| 0.1.0 | 001-esqueleto | `GET /health`, `GET /status` |
| 0.2.0 | 005-api | Aditivo: `/eventos`, `/eventos/mapa`, `/recuentos/{pais,subregion,hora}`, `/distribuciones/{magnitud,profundidad}`, `/comparacion-historica`; `/status` añade `ultima_ingesta_correcta`, `periodo_consultado`, `datos_desactualizados` y `umbral_datos_desactualizados_segundos` (los campos de la 0.1.0 no cambian); filtros comunes, errores 400/503/500 genéricos y CORS (`GET`/`OPTIONS`, `ngrok-skip-browser-warning`) |
