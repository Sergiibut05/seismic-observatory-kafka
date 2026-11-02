# Plan 005 (compacto)

La API sigue siendo de solo lectura sobre `live.evento_actual` (+ `ingesta.pais`) y, solo para
la comparación, sobre una tabla nueva con 2025. No crea tablas, no lee `replay.*`, no tiene
dependencias nuevas (FastAPI, psycopg 3 y Starlette ya están; los tests no usan `httpx`).

## Decisiones

1. **Almacén de 2025 (FR-012)**: tabla `historico.evento_2025` (esquema propio `historico`, ni
   `live` ni `replay`). Una fila por `event_id`; `CHECK` de ocurrencia dentro de 2025 (así el
   denominador es siempre 365 días y la consulta no filtra por fecha). País por el mismo
   `IndicePaises` (`common/catalogo.py`), guardado como código + nombre, con FK a `ingesta.pais`.
   Sin `source`/`mode`/`sintetico`: todo es USGS real. Carga: `python -m
   observatorio.historico_cargar` (`docker compose exec producer …`), que lee
   `HISTORICO_DIR/2025/eventos.geojson`, reutiliza `consumer.calidad.evaluar` (lo inservible se
   registra con `result=rechazado` y no se carga; nunca se rellena con 0), crea esquema y tabla con
   `IF NOT EXISTS`, inserta `ingesta.pais` con `ON CONFLICT DO NOTHING` (para que la FK valga aunque el
   consumidor no haya arrancado) y hace el upsert en **una transacción** con la misma regla de
   `updated` más reciente: repetirla no cambia nada. Montaje nuevo: `./catalogo:/catalogo:ro` y
   `CATALOGO_PATH` también en `producer` (único servicio que ya monta `data/historico`; la `api`
   no monta nada). `db/init/005_api.sql` crea lo mismo para volúmenes nuevos; el cargador lo crea
   en volúmenes antiguos. **No cargado**: la API mira `to_regclass('historico.evento_2025')` y
   `EXISTS(SELECT 1 …)` antes de agregar (una tabla inexistente en `consultar` cerraría la
   conexión) y responde 200 con `historico_2025.estado="no_cargado"`, `media_diaria=null`,
   `cociente=null` y el recuento real de las 24 h. Nunca un 0 inventado.
2. **Código**: `api/filtros.py` (puro: `leer_filtros`, `leer_ventana`, `leer_paginacion` y
   `construir_where`, que solo concatena fragmentos constantes con `%s`; el texto del usuario va
   en `params`), `api/consultas.py` (constantes SQL + `sql_lista(where)`; todo `SELECT`),
   `api/calculos.py` (puro: `rellenar_horas`, `armar_intervalos`, `comparar`, `geojson_mapa`,
   `desactualizado`), `api/rutas.py` (`APIRouter` con los endpoints, `ejecutar()` que traduce
   `SinConexion`/`psycopg.Error`/timeout a `ServicioNoDisponible`), `main.py` (CORS, manejadores
   400/503/500 con cuerpo genérico). Puro con pytest: validación, WHERE, horas con cero, intervalos
   con negativos y «sin valor», media y cociente, tope del mapa, umbral, configuración de CORS y
   que cada SQL empieza por `SELECT`. Solo en vivo (verifier): SQL real, índices, preflight,
   405/404, 503 con PostgreSQL parado y tiempos.
3. **Conexión y tiempos**: una conexión con lock basta: el panel hace ~8 peticiones/min por
   cliente de ≤ 50 ms con 20.000 filas (≈ 0,4 s de lock por minuto y cliente, < 1 % con 10
   clientes). Coste: una consulta lenta (comparación, ≤ 3 s) retrasa a las demás. `timeout` de
   consulta **5 s** (el objetivo es ≤ 3 s, así un timeout es un fallo real y no un falso positivo).
   Un fallo o un timeout pierde la conexión (`Database` ya lo hace) y las peticiones en cola
   reciben 503 hasta reconectar con backoff: aceptable. No se introduce pool: tocaría `db.py`,
   compartido con el consumidor (transacciones bajo el lock) para un problema no medido. Se
   revisa si T10 mide espera de lock > 1 s. `SET default_transaction_read_only` no se
   añade: el usuario es el mismo del resto; la garantía es que `consultas.py` solo tiene `SELECT` (test).
   **Índices** (medio / peor caso en la tabla de abajo):
   `live.evento_actual`: PK `event_id` (existe; búsqueda por identificador, upsert);
   **nuevo** `evento_actual_ocurrencia_idx (ocurrencia DESC, event_id)` (lista paginada sin
   ordenar, rango `desde/hasta`, ventanas horarias, últimas 24 h y `min/max(ocurrencia)` del
   periodo; coste: un índice más por upsert, ~1 MB con 20.000 filas, +~250 escrituras/día). Se
   crea en `005_api.sql` y en `_DDL` del consumidor (volúmenes antiguos; la API no crea nada). El
   filtro de país es por `pais_codigo`, así que `(pais_nombre, ocurrencia)` no se usa: queda sin
   tocar; `(pais_codigo, ocurrencia)` solo se añade si T10 mide > 1 s. `historico.evento_2025`: solo PK
   `event_id` (carga idempotente). Sin índice secundario: el denominador recorre un año entero o
   un país (18.302 filas ≈ ms; un índice no evita leer el año). Con 100 M de filas: BRIN sobre
   `ocurrencia`, particionado por mes y agregado diario precalculado (informe §10).
   `ingesta.consultas`: se lee con `ORDER BY id DESC LIMIT 1` sobre la PK (para en la primera fila válida).
4. **CORS y umbral**: `CORS_ORIGEN_NETLIFY` (opcional, sin valor por defecto; vacía = solo
   `http://localhost:4200`, con aviso `result=aviso` en el log). Obligatoria bloquearía el
   `docker compose up` de 001–005 antes de existir la URL de Netlify (006). Se valida al arrancar:
   `https://host[:puerto]` sin ruta, `/` final ni `*`; si no, `ConfigError` (exit 2, sin el valor).
   `CORSMiddleware`: orígenes exactos, `allow_methods=[GET, OPTIONS]`,
   `allow_headers=[ngrok-skip-browser-warning]` (Accept y Content-Type ya están permitidos por
   Starlette), `allow_credentials=False`, `max_age=600`. `DATOS_DESACTUALIZADOS_SEGUNDOS`
   (defecto **300**, entero ≥ 60): el productor consulta cada 60 s y puede perder 1-2 pasadas por
   un 5xx o un timeout sin que el panel parpadee; con 5 ciclos sin éxito el aviso salta en minutos.
5. **Última ingesta correcta**: `ingesta.consultas` ya la escribe el productor tras cada pasada
   buena (`http_status=200`, `error NULL`; los fallos van con `error` informado): el productor no
   cambia. `SELECT acabada_en … WHERE http_status = 200 AND error IS NULL ORDER BY id DESC LIMIT 1`.
   Periodo: `min/max(ocurrencia)` de `NOT sintetico`. Con la base caída los tres campos nuevos van a `null`.
6. **Mapa**: tope fijo `MAPA_TOPE = 5000` (Leaflet con canvas aguanta ese orden; ~1 MB por ngrok).
   Devuelve los más recientes; si hay más, `truncado=true` y `total` real. GeoJSON
   `FeatureCollection` (`L.geoJSON(datos, {pointToLayer})` lo consume sin transformar; miembros
   propios `total`, `devueltos`, `limite`, `truncado`, `generated_at`), coordenadas `[lon, lat]`
   (la profundidad va en `properties`, no como tercera coordenada). La lista es JSON plano.
   Lista: `limite` 1-500 (defecto 100), `desplazamiento` 0-100.000.

## Endpoints (todos `GET`; el resto, 405)

| Ruta | Respuesta (resumen) |
| --- | --- |
| `/health`, `/status` | 0.1.0 + `ultima_ingesta_correcta`, `periodo_consultado{desde,hasta}`, `datos_desactualizados`, `umbral_datos_desactualizados_segundos` (los nuevos `null` sin base) |
| `/eventos` | `{eventos[{event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud, pais_codigo, pais_nombre, subregion, sintetico}], total, limite, desplazamiento}`; orden `ocurrencia DESC, event_id ASC` |
| `/eventos/mapa` | GeoJSON; `properties`: `event_id, ocurrencia, updated, magnitud, profundidad, pais_nombre, sintetico` |
| `/recuentos/pais` | `{total, categorias[{codigo, nombre, recuento}]}`; «Sin país asignado» con `codigo=null` |
| `/recuentos/subregion` | `{total, categorias[{nombre, recuento}]}`; sin país → «Sin país asignado» |
| `/recuentos/hora` | `{desde, hasta, total, ventanas[{inicio, recuento}]}`; todas las horas UTC, con ceros |
| `/distribuciones/magnitud`, `/distribuciones/profundidad` | `{unidad, total, sin_valor, intervalos[{desde, hasta, etiqueta, recuento}]}` |
| `/comparacion-historica` | `{ventana_actual{desde,hasta,eventos}, historico_2025{estado, eventos, dias, media_diaria}, cociente, filtros_efectivos, aviso, generated_at}` |

Errores: 400 `{"error":"parametro_invalido","parametro":"magnitud_min"}`; 503
`{"error":"servicio_no_disponible"}`; 500 `{"error":"error_interno"}`. Nada de SQL, rutas ni
trazas. Los parámetros desconocidos o repetidos son 400.

## Parámetros

| Parámetro | Endpoints | Regla |
| --- | --- | --- |
| `desde`, `hasta` | todos menos `/comparacion-historica` | ISO 8601 con `Z` u offset (sin zona = 400), a UTC; `desde` ≥, `hasta` <; `desde < hasta`. Solo `/recuentos/hora`: sin ellos, últimas 24 h; máx. 31 días |
| `magnitud_min`, `magnitud_max` | todos | finito, −10 a 10, `min ≤ max`. Con filtro, la magnitud nula queda fuera |
| `pais` | todos | `^[A-Z]{3}$` (`ADM0_A3`; el catálogo no tiene otros) o «Sin país asignado» (`pais_codigo IS NULL`) |
| `subregion` | todos | texto ≤ 80, sin control; igualdad con `ingesta.pais.subregion`; «Sin país asignado» = sin país. Con `pais`, se combinan con Y |
| `incluir_sinteticos` | todos menos `/comparacion-historica` | `true`/`false` (defecto `false`) |
| `limite`, `desplazamiento` | `/eventos` | ver 6 |

Intervalos (`width_bucket` sobre un array de bordes; el Python rellena los vacíos):
magnitud `<0, 0–1, …, 8–9, ≥9`; profundidad km `<0, 0–10, 10–30, 30–70, 70–150, 150–300, 300–500, 500–700, ≥700`.
Horas: `date_trunc('hour', ocurrencia, 'UTC')`; el SQL solo devuelve las no vacías, `rellenar_horas` añade los
ceros; el primer/último bucket puede ser parcial si `desde`/`hasta` no son horas en punto.
Comparación: ventana `[generated_at − 24 h, generated_at]`, `NOT sintetico`, magnitud mínima
efectiva `max(4, pedida)`, `magnitud_max`, `pais`, `subregion`; `media_diaria = n_2025 / 365`;
`cociente = n_24h / media` (`null` si la media es 0 o el histórico no está cargado); `aviso` fijo
(último periodo incompleto por retrasos y revisiones, y «histórico no cargado» si procede).

## Esquema SQL esencial (`db/init/005_api.sql`, idempotente)

```sql
CREATE SCHEMA IF NOT EXISTS historico;
CREATE TABLE IF NOT EXISTS historico.evento_2025 (
    event_id    text PRIMARY KEY CHECK (event_id <> ''),
    updated     timestamptz      NOT NULL,
    ocurrencia  timestamptz      NOT NULL
        CHECK (ocurrencia >= '2025-01-01Z' AND ocurrencia < '2026-01-01Z'),
    magnitud    double precision,
    profundidad double precision,
    longitud    double precision NOT NULL,
    latitud     double precision NOT NULL,
    pais_codigo text REFERENCES ingesta.pais (codigo),
    pais_nombre text             NOT NULL,
    cargado_en  timestamptz      NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS evento_actual_ocurrencia_idx
    ON live.evento_actual (ocurrencia DESC, event_id);
INSERT INTO ingesta.version_esquema (version, nombre) VALUES (5, 'api') ON CONFLICT (version) DO NOTHING;
```

## Coste (§10)

| Operación | Estructura | Medio | Peor caso |
| --- | --- | --- | --- |
| Buscar versión/evento por `event_id` | btree PK | O(log n) | O(log n) (árbol equilibrado); sin índice O(n) |
| País de un punto (consumidor y cargador) | `STRtree` de 242 polígonos | O(log m + k) | O(m) si todas las cajas contienen el punto; secuencial O(m·v). La API no hace geometría: lee el país ya asignado |
| Lista paginada | índice `(ocurrencia DESC, event_id)` | O(log n + desplazamiento + límite) | sin índice O(n log límite) (top-N) |
| Horas / recuentos con rango | índice por `ocurrencia` + agregado hash | O(log n + r) | O(n) sin rango; relleno de ceros O(h), h ≤ 745 |
| Comparación 2025 | recorrido de la tabla + `count` | O(n₂₀₂₅) | igual: un año entero se lee siempre |

## Constitution Check

I sin servicios nuevos (solo un montaje en `producer`). II contrato 0.2.0 aditivo, instantes UTC con
ms. III la API no escribe; el cargador es idempotente y transaccional. IV cifras del estado actual,
nunca de mensajes; 2025 aparte y rechazos con motivo en el log. V país por polígono (`ADM0_A3`), «Sin país
asignado» en todas las agregaciones. VI nada lee `replay.*`; sintéticos solo con `incluir_sinteticos`.
VII solo GET/OPTIONS, sin `/docs` ni admin, CORS exacto sin credenciales, sin secretos. VIII módulos
pequeños, sin pool ni ORM y con medición en T10.

## Desviaciones

- API: el aviso de CORS vacío usa `result=info` con `level=WARNING` y `aviso=…` (el conjunto cerrado de `result` no tiene «aviso»).
- API: se añade `SinCorsParaOrigenAjeno` (ASGI, 20 líneas) porque el preflight de Starlette devuelve `allow-methods`/`allow-headers` incluso a un origen no autorizado y AC-9 pide cero cabeceras CORS.
- API: el 500 genérico se resuelve en el middleware de acceso (no con `exception_handler(Exception)`) para que quede dentro de CORS y el panel reciba el 500, no un fallo de CORS.
- API: `/status` informa siempre `umbral_datos_desactualizados_segundos` (es configuración); `periodo_consultado` es `null` (no `{desde:null,hasta:null}`) sin eventos reales; `/recuentos/subregion` nombra «Sin subregión» a un país sin subregión en el catálogo (hoy ninguno).