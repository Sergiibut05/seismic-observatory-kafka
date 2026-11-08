# Plan 007 (compacto)

Es sobre todo documentación; el código nuevo es el mínimo para tener evidencia real. Cuatro piezas de
código: (A) `modo` en la API (contrato 0.3.0) y casos controlados, (B) selector REPRODUCCIÓN e
interruptor de sintéticos en el panel, (C) un script de mediciones y (D) la memoria. Sin
dependencias nuevas (Python: `time`, `tracemalloc`, `statistics`, `shapely` y `psycopg` ya están;
Angular: nada), sin servicios nuevos, sin tablas nuevas en `live`, `replay` ni `historico`, y
`compose.yaml` no cambia (el productor ya monta `catalogo/` y tiene las variables de PostgreSQL).

## Decisiones

1. **REPRODUCCIÓN en la API (FR-019)**: parámetro `modo` (`live` por defecto | `replay`) en
   `/eventos`, `/eventos/mapa`, `/recuentos/{pais,subregion,hora}` y `/distribuciones/{magnitud,profundidad}`.
   `Filtros` gana `modo: str = "live"`; `PARAMS_FILTRO` incluye `modo`; `leer_filtros` valida que sea
   `live` o `replay` (otro valor, o repetido → 400 `parametro=modo`). La tabla sale de un
   diccionario cerrado `TABLAS = {"live": "live.evento_actual", "replay": "replay.evento_actual"}`
   y se inserta en la plantilla con `{tabla}` junto a `{where}` (`con_where(sql, donde, modo)`):
   el texto del usuario nunca llega al SQL, solo la clave del diccionario. **Estado actual, no versiones**:
   las cifras salen de `replay.evento_actual` (Constitución IV), no hace falta `replay.versiones_evento`.
   **Tiempos**: `ocurrencia` es el tiempo original (`properties.time`); el de reproducción ya se guarda:
   `observatorio.replay` fija `ingested_at` al publicar cada mensaje (`replay.py`, «tiempo de
   reproducción») y `003/004` lo almacenan en `replay.evento_actual.ingested_at`, así que no cambia
   ninguna tabla. La API lo expone como **`reproducido_en`** en cada evento de `/eventos` y en
   `properties` de `/eventos/mapa` (`null` en live: allí `ingested_at` es ingesta, no reproducción).
   Toda respuesta lleva `"modo": "live"|"replay"` (el mapa, como miembro propio de la
   `FeatureCollection`). `/comparacion-historica` acepta `modo=live` y rechaza `modo=replay` con 400
   `parametro=modo` (es la única regla nueva en `PARAMS_COMPARACION`). `/status` añade
   `eventos_replay` (entero, `null` sin base): primero `to_regclass('replay.evento_actual')` y luego
   `count(*)`, como el histórico, porque una tabla inexistente en `consultar` cerraría la conexión.
   **Ventana de `/recuentos/hora` en replay**: sin `desde`/`hasta`, «últimas 24 h» daría 24 ceros (los
   eventos son de 2025); en replay la ventana por defecto termina en `max(ocurrencia) + 1 ms` de
   `replay.evento_actual` (una consulta más) y retrocede 24 h; con filtros explícitos, igual que live. Coste y
   límite: la ventana de 24 h puede no cubrir toda una reproducción larga; se avisa en el contrato.
   **Índices**: ninguno nuevo; `replay.evento_actual` solo tiene PK y `(pais_nombre, ocurrencia)`: la
   lista ordena por `ocurrencia` con top-N en memoria (`O(n log límite)`), aceptable con la
   reproducción acotada (decenas o pocos miles de filas; el `EXPLAIN` real va en la memoria). Un índice como
   el de live costaría una escritura más por evento sin beneficio medido.
2. **Casos controlados (FR-012)**: `backend/observatorio/producer/casos.py`, módulo nuevo junto a
   `smoke` (se prefiere a ampliar `smoke`, que es la prueba de humo de 001 con sus tests y su salida
   estable). Reutiliza `smoke._preparar` (productor `acks=all`, idempotente, topic asegurado),
   `contrato.construir_mensaje` y el log `result=publicado` tras el acuse. Uso:
   `docker compose exec producer python -m observatorio.producer.casos [--listar] [--solo NOMBRE …] [--base ISO]`.
   `source = synthetic-casos`; todos los ids empiezan por `synthetic-caso-` (el `CHECK` de las tablas
   exige prefijo en `source` e `id`). `--base` (por defecto la hora UTC en curso, truncada) fija
   `time` y `updated`: **repetir el comando en la misma hora reenvía exactamente las mismas versiones**
   (idempotencia comprobable) y la ocurrencia es reciente (visible con los filtros por defecto).

   | Caso | Mensajes (id; `updated`; resto) | Resultado esperado |
   | --- | --- | --- |
   | `nuevo` | `synthetic-caso-nuevo`; B; M 3.4, `[-3.7, 40.4, 10]` (España) | una fila actual y una versión |
   | `reenvio` | el mismo mensaje otra vez (otro `ingested_at`) | recuento igual; log `result=omitido` |
   | `revision` | `…-revision` v1 (B; M 2.0, España) → v2 (B+60 s; M 4.5, `[2.3, 48.9, 8]` Francia) | actual = v2; recuento por país España −1, Francia +1; 2 versiones |
   | `antigua` | `…-revision` con `updated` B−60 s (M 9.0) tras v2 | actual no cambia; 3 versiones (historial intacto) |
   | `magnitud_nula` | `…-magnitud-nula`; M `null` | `magnitud` NULL; «ND» en el panel; `sin_valor` +1 |
   | `coordenadas_invalidas` | `…-coordenadas-invalidas`; lon 200 | `ingesta.cuarentena` (`coordenadas_fuera_de_rango`), clave `synthetic-…`; nada en `live.*` |
   | `mar` | `…-mar`; `[-30, 0, 10]` | pais_codigo NULL, «Sin país asignado», cuenta en los recuentos |
   | `profundidad_negativa` | `…-profundidad-negativa`; prof. −2 | se conserva −2 (intervalo `< 0`) |

   Código puro y probable sin Kafka: `construir_casos(base) -> list[Caso]` (nombre, clave, valor) y
   `seleccionar(casos, nombres)`; `publicar()` es el único que toca Kafka. Replay (duplicado y revisión)
   ya lo hace `observatorio.replay`; no se repite aquí.
3. **Limpieza (FR-012, AC-15)**: hoy `scripts/borrar_sinteticos.sql` solo borra `live.versiones_evento`
   (deja el estado actual y la cuarentena). Pasa a una transacción que borra, en este orden:
   `live.evento_actual WHERE sintetico`, `live.versiones_evento WHERE sintetico`, `replay.evento_actual` y
   `replay.versiones_evento WHERE sintetico` (por si alguien publicó casos allí) y
   `ingesta.cuarentena`. **Cuarentena sin columna `sintetico`**: `clave` (bytea) guarda el `id` del evento, así
   que se identifica con `substring(clave from 1 for 10) = 'synthetic-'::bytea` (no se usa
   `convert_from`: fallaría con claves no UTF-8 reales). Cada `DELETE` lleva `RETURNING`/`\echo` de su
   recuento y el script acaba con un `SELECT` de comprobación (todo 0). Lo real no se toca: las tres
   condiciones son por `sintetico` o por prefijo, y el `CHECK` impide un real con ese prefijo. Los
   mensajes siguen en Kafka hasta la retención (7 días): reaplicar el consumo no los recrea porque el
   grupo ya confirmó su offset. Es idempotente (segunda ejecución: 0 filas).
4. **Mediciones (FR-008, FR-009, FR-010)**: `backend/observatorio/mediciones.py`, ejecutado con
   `docker compose exec -T producer python -m observatorio.mediciones --tamanos 1000,10000,100000 --repeticiones 5 | Set-Content -Encoding utf8 docs/memoria/mediciones.md`
   (con `Set-Content`: la redirección `>` de Windows PowerShell 5 escribe UTF-16). Tres bloques:
   - **Memoria** (Python, `perf_counter` + `tracemalloc`, `N ∈ {1.000, 10.000, 100.000}`): (a) búsqueda de la
     última versión por id: lista de tuplas con recorrido secuencial frente a diccionario, 200 búsquedas
     aleatorias con semilla fija (se mide construcción y búsqueda por separado); (b) país: recorrido
     secuencial de los 242 polígonos del catálogo real (`catalogo/paises.geojson`, `shapely`,
     `covers`) frente a `IndicePaises.asignar` (`STRtree`), sobre `N` puntos pseudoaleatorios
     con semilla fija (el secuencial con 100.000 puntos son ~24 M de pruebas: **una repetición** y se
     declara; el resto, 5); comprueba que ambos dan el mismo país; (c) agregación por ventana horaria:
     `dict` acumulando `hora → recuento` sobre `N` instantes frente a ordenar y agrupar; el
     `GROUP BY` equivalente va en SQL. Por cada medida: mediana y máximo de las repeticiones, pico de
     `tracemalloc` en KiB (medido en una pasada aparte: `tracemalloc` ralentiza).
   - **PostgreSQL** (esquema `medicion`, creado con `DROP SCHEMA IF EXISTS medicion CASCADE` al empezar y
     al terminar, en un `finally`): tabla `medicion.evento` con la forma de `live.evento_actual` sin FKs, `N`
     filas con id `synthetic-medicion-<i>` y `sintetico = true` (así, si algo se quedara, el borrado lo
     reconocería). Sin índices: `EXPLAIN (ANALYZE, BUFFERS)` de (i) búsqueda por `event_id`, (ii) lista
     paginada `ORDER BY ocurrencia DESC LIMIT 100`, (iii) ventana horaria con `GROUP BY date_trunc('hour', …)` en
     un rango de 24 h. Después `ALTER TABLE … ADD PRIMARY KEY (event_id)` y `CREATE INDEX (ocurrencia DESC,
     event_id)`, `ANALYZE` y las mismas tres consultas. Se guardan el plan (texto), `Execution Time`, buffers
     (`shared hit/read`) y `pg_total_relation_size` de tabla e índices por tamaño. Estadístico: mediana de 5
     ejecuciones del plan.
   - **Garantía**: antes y después se leen `count(*)` de `live.evento_actual`, `live.versiones_evento`,
     `replay.evento_actual` e `historico.evento_2025`; si no coinciden, exit 1 y el mensaje lo dice. El
     script **nunca** escribe fuera de `medicion` (un test comprueba que cada sentencia de escritura
     menciona `medicion.`). Equipo: el script imprime `platform`, `python`, `psycopg`, `shapely`,
     versión de PostgreSQL y CPU/RAM del contenedor (`os.cpu_count`, `/proc/meminfo`); la CPU, RAM y disco del
     anfitrión Windows los anota D con `Get-CimInstance` (el contenedor corre en la VM de Docker y no lo ve).
   Salida: Markdown con fecha UTC, equipo, procedimiento, tablas y planes; se guarda en `docs/memoria/mediciones.md` y
   se copia a `specs/007-memoria/evidencias/mediciones.md`. Con 100 millones el informe **extrapola** (lineal
   para el recorrido, logarítmico para el índice, memoria = bytes por fila medidos × 10⁸) y lo rotula como tal.
5. **Panel (FR-013, FR-020)**: componente nuevo `componentes/vista-datos/` (selector «Datos: En directo /
   REPRODUCCIÓN», interruptor «Incluir casos de prueba sintéticos» y las dos franjas) colocado entre la cabecera
   y los filtros. Estado en `FiltrosStore`: `vista = signal<{modo: 'live'|'replay', sinteticos: boolean}>`
   (por defecto `live` y `false`; sin `localStorage`: se pierde al recargar, como pide FR-013).
   `fijarModo()` y `fijarSinteticos()` aplican **al instante** (sin los 400 ms de debounce: no es texto) y
   devuelven la tabla a la página 0. `RefrescoService` también observa `vista()` y pide una ronda
   (la cola ya coalesce). `aQuery(filtros, modo, extra, ahoraMs, vista = VISTA_VIVO)`: añade `modo=replay`
   solo si es replay e `incluir_sinteticos=true` solo si está activo; **nunca** en `comparacion`.
   En replay `PanelDatosService` no pide `/comparacion-historica` (8 GET por ronda en vez de 9) y el
   bloque muestra «La comparación histórica solo existe en directo». Visual: franja «REPRODUCCIÓN»
   (`role="status"`, texto grande, borde discontinuo y fondo distinto: no depende solo del color) mientras
   `modo = replay`; aviso permanente «Casos de prueba sintéticos incluidos: no son terremotos reales» con
   el interruptor activo; tabla con columna «Reproducido (UTC)» solo en replay y insignia «SINTÉTICO» en la
   fila; mapa con marcador de contorno discontinuo y ficha con «SINTÉTICO» y, en replay, «Reproducido». El texto
   «Solo se muestran eventos reales» de `filtros.html` pasa a depender de la vista. Las capturas del análisis se
   hacen con el interruptor apagado. Se enmienda `specs/006-panel/spec.md` (FR-007: «sin sintéticos» → «apagado por
   defecto, con marca y aviso») y se añade una nota de enmienda al principio.
6. **Contrato 0.3.0**: `docs/CONTRATO-API.md` y `specs/001-esqueleto/contracts/api.openapi.yaml` pasan de 0.2.0 a
   0.3.0, aditivo (los campos de 0.2.0 no cambian): parámetro `modo` en 7 endpoints (más `modo=live|replay` en
   la comparación, con el 400), campo `modo` en las respuestas, `reproducido_en` en eventos y `eventos_replay`
   en `/status`. Tabla de cambios y ejemplos reales de replay (recortados). Se anota la enmienda en `specs/005-api/spec.md`.
7. **Memoria (FR-001 a FR-018)**: un único `docs/MEMORIA.md` (índice y cada sección) y, como apoyo,
   `docs/memoria/consultas.sql` (todas las consultas con las que se obtiene cada cifra, numeradas Q01…, ejecutables
   copiando con `docker compose exec -T postgres psql -U observatorio -d observatorio -f -`) y
   `docs/memoria/mediciones.md`. Cada cifra: consulta (`Qnn`) o comando + fecha de medición. Las capturas
   viven en `specs/007-memoria/evidencias/` y `specs/006-panel/evidencias/`; los enlaces son relativos. Las
   secciones de la persona (explicación individual, URL de Netlify) son `[ESCRIBE: …]` y `PENDIENTE (alumno)`:
   ningún agente las rellena. La memoria se escribe en dos pasadas: D (sin capturas, con cifras SQL) y F (tabla de
   aceptación, conclusiones con captura, rúbrica final).
8. **Verificación**: el `verifier` ejecuta `/speckit-analyze` antes (T0) y, después, las pruebas §11 con los
   casos de la decisión 2 (`restart consumer` con un lote publicado; `stop api`/`start api` en ≤ 60 s; replay),
   y T11 de 006 con `cursor-ide-browser` en `http://localhost:4200`. No cambia código de producción: un
   fallo vuelve al `developer`. Los datos sintéticos se borran al final con el script de la decisión 3 y el
   recuento de reales debe ser el de antes.

## Contrato 0.3.0 (resumen)

| Cambio | Detalle |
| --- | --- |
| `modo` (parámetro) | `live` (defecto) \| `replay`; `/eventos`, `/eventos/mapa`, `/recuentos/*`, `/distribuciones/*`. `/comparacion-historica`: `live` vale, `replay` → 400 `{"error":"parametro_invalido","parametro":"modo"}`. Otro valor o repetido → 400 |
| `modo` (respuesta) | en todas: `"modo": "live"` \| `"replay"` (el mapa, junto a `total`, `devueltos`…) |
| `reproducido_en` | `/eventos` (`eventos[]`) y `properties` del mapa: instante UTC en replay (= `ingested_at`), `null` en live |
| `/status` | `eventos_replay`: entero o `null` (base caída) |
| `/recuentos/hora` en replay | sin `desde`/`hasta`: 24 h que terminan en el último `ocurrencia` replay |
| Sin cambios | rutas, `incluir_sinteticos` (rige también en replay), errores 503/500, CORS, límites |

## Coste (§10)

| Operación | Estructura | Medio | Peor caso |
| --- | --- | --- | --- |
| Última versión por id | lista de tuplas / `dict` / PK de PostgreSQL | lista O(n); `dict` O(1); btree O(log n) | lista O(n); `dict` O(n) con colisiones (teórico); btree O(log n) |
| País de un punto | recorrido secuencial / `STRtree` (242 polígonos) | secuencial O(m·v); `STRtree` O(log m + k) | secuencial O(m·v); `STRtree` O(m) si todas las cajas contienen el punto |
| Agregación por hora | `dict` de contadores / ordenar y agrupar / `GROUP BY` | `dict` O(n); ordenar O(n log n); `GROUP BY` hash O(n) (con rango e índice O(log n + r)) | igual; `GROUP BY` con disco O(n log n) si no cabe en `work_mem` |
| Lista paginada con `modo=replay` | top-N sobre `replay.evento_actual` | O(n log límite) | igual (sin índice de `ocurrencia`) |
| Medición completa | tres bloques × 3 tamaños × 5 repeticiones | ~minutos (el secuencial de país con 100.000 puntos domina) | `--tamanos` y `--repeticiones` lo acotan |

## Constitution Check

I sin servicios nuevos ni cambios en `compose.yaml`. II contrato 0.3.0 aditivo, UTC con ms, `modo` y
`reproducido_en` explícitos. III `mediciones` solo escribe en el esquema `medicion` y lo borra; `casos` publica
por Kafka con acuse y el consumidor confirma tras el `COMMIT`; la limpieza es idempotente. IV cifras del
estado actual, nunca de mensajes; replay aislado en su tabla. V «Sin país asignado» en el caso `mar` y en
toda agregación. VI **cumplida**: REPRODUCCIÓN en API y panel, tiempo original y de reproducción, sintéticos
fuera por defecto y con marca. VII solo `GET`; `modo` sale de una lista cerrada, no se concatena; sin
secretos (authtoken de ngrok y URL de Netlify fuera de Git). VIII transparencia: el proceso real (qué hizo cada
subagente y qué no se verificó) va tal cual en la memoria, sin maquillar.

## Desviaciones

- `casos.py` es módulo propio y no una ampliación de `smoke`: `smoke` es la prueba de humo de 001 (un evento fijo) y su salida y tests quedan intactos.
- `reproducido_en` reutiliza `ingested_at` de `replay.evento_actual` (ya guardado): no hay columna ni migración nueva.
- En replay no hay `incluir_sinteticos` propio: rige el mismo parámetro y la misma regla (`sintetico`), aunque `observatorio.replay` solo publica datos reales.
- `/recuentos/hora` en replay usa una ventana anclada al último evento y no «últimas 24 h»; es una excepción documentada al comportamiento de live.
- El secuencial de país con 100.000 puntos se mide con una sola repetición (coste ~minutos); mediana y máximo coinciden y se declara.
- `scripts/borrar_sinteticos.sql` no tiene test pytest (la imagen no incluye `scripts/`): lo prueba el `developer` en vivo y lo repite el `verifier`.
