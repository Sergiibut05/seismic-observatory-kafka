# Research 013

## Por qué una segunda fuente

- **Medición (2026-11-12, 24 h)**: Europa (lat 34–72, lon −25–45): USGS 0, EMSC 98. EE. UU. continental: USGS 132, EMSC 19. Mundo: USGS 239, EMSC 305.
- **Causa**: el feed de USGS es el catálogo de USGS: pequeña sismicidad de EE. UU. y, del resto, sobre todo M ≥ 4,5. EMSC agrega las redes nacionales europeas.
- **Decisión**: USGS + EMSC. Ninguna de las dos basta sola (EMSC pierde la mayoría de EE. UU.; USGS deja Europa vacía). Para M ≥ 4 coinciden en un 97 % del recuento anual de 2025 (18.305 frente a 17.768).
- **Descartadas por ahora**: INGV (EMSC ya lo agrega), GEOFON (lenta: 4 s por consulta pequeña), AFAD (solo Turquía), ISC (boletín con horas de retraso y flojo en lo reciente: 5 eventos en Europa en 48 h frente a 280 de EMSC; un mes M ≥ 2,5 tarda 74 s), EarthScope/IRIS (retirado el 1-jun-2026).

## EMSC

- **Acceso**: FDSN en `https://www.seismicportal.eu/fdsnws/event/1/query?format=json`. Probado: 200 en 0,5–1,4 s.
- **Formato**: GeoJSON. `id` = `properties.unid`; `time` y `lastupdate` en ISO 8601 UTC; `mag`, `magtype`, `flynn_region`, `auth`, `evtype`, `depth`, `lat`, `lon`.
- **Profundidad**: la geometría la trae negativa (`[lon, lat, -23.0]`) y `properties.depth` positiva (23.0). Se usa `properties.depth`, en km hacia abajo, como USGS.
- **Tipo**: en 3 días, 1.374 `ke` (terremoto conocido), 6 `se` (sospechoso), 3 `ue` (desconocido). Solo `ke` se publica; el resto va a exclusiones con motivo, igual que los `type != earthquake` de USGS.
- **Límite**: corta a unas 10.000 filas por consulta **sin avisar** (marzo de 2025, todas las magnitudes: `count` 109.952, devueltas 9.952). Por eso el relleno cuenta antes (`/count`) y parte el intervalo hasta que cabe con margen (≤ 8.000).
- **Sondeo en directo**: ventana de 26 h (24 h como el feed de USGS y 2 h de margen) con `limit=10000`. En 24 h EMSC da del orden de 300–1.400 eventos: cabe. Las revisiones de eventos de hace más de 26 h no se ven, igual que con el feed de USGS.
- **Alternativa descartada**: WebSocket (`standing_order`). Más inmediato, pero añade un cliente distinto y reconexiones; el enunciado pide consultar cada 60 s y así los dos productores son el mismo código.
- **Licencia**: CC BY 4.0, con atribución «EMSC» en el panel y en `docs/FUENTES-Y-LICENCIAS.md`.

## Regla de fusión: medida, no supuesta

Script en `evidencias/umbrales.py`. Para cada evento USGS se busca el EMSC más próximo en una ventana amplia (120 s, 300 km) y se miden las diferencias.

| | Enero 2025, M ≥ 4 (1.413 USGS) | 1–7 junio 2025, M ≥ 2,5 (469 USGS) |
|---|---|---|
| Con pareja EMSC en la ventana amplia | 78,3 % | 83,2 % |
| Δt mediana / p95 / p99 | 0,6 / 6,0 / 52,5 s | 0,4 / 3,6 / 8,8 s |
| Distancia mediana / p95 / p99 | 8,4 / 44,5 / 104,6 km | 3,3 / 24,9 / 53,2 km |
| Δmagnitud p95 | 0,4 | 0,4 |
| Emparejados con ≤ 30 s y ≤ 100 km | 76,4 % (97,6 % de los que tienen pareja) | 82,7 % (99,4 %) |
| Parejas USGS–USGS a ≤ 30 s y ≤ 100 km | 7 | 2 |

- **Decisión**: ≤ 30 s y ≤ 100 km. Ampliar a 60 s y 150 km solo gana un 0,8 % y dobla las parejas ambiguas (16 réplicas USGS–USGS en enero).
- **Las réplicas**: hay parejas reales de la misma fuente dentro de la ventana. Por eso dos informes de la misma fuente nunca se fusionan y un evento tiene como mucho un informe por fuente; si un informe tiene dos candidatos, gana el de menor puntuación `Δt/30 s + d/100 km`.
- **La magnitud no decide**: difieren poco (p95 0,4) pero en escalas distintas (`mb`, `ml`, `mw`); usarla añadiría falsos negativos sin quitar falsos positivos.
- **El 22 % sin pareja** no es un problema de la regla: son eventos que solo publica una fuente (por cobertura o por magnitud distinta). Quedan como eventos de una sola fuente.

## Dónde vive el estado de la fusión

- **Decisión**: en PostgreSQL (esquema `fusion`), no en el estado de Spark. Cada micro-lote lee los informes de su ventana de tiempo, decide y guarda.
- **Razón**: el relleno trae eventos de hace meses. Con el estado en Spark (`applyInPandasWithState` y un *watermark*) esos informes llegarían «tarde» y se descartarían, o habría que mantener estado de dos años en memoria. En PostgreSQL basta un índice por hora.
- **Quién escribe qué**: la fusión es dueña de `fusion.*` (como el consumidor lo es de sus offsets); las tablas analíticas (`live.*`) solo las escribe el consumidor (constitución III).

## Qué hace Spark y qué hace Python

- **Spark**: lectura de los dos topics con offsets en *checkpoint*, micro-lotes con tope de tamaño (`maxOffsetsPerTrigger`), extracción de id y versión con funciones JSON de Spark SQL y deduplicación dentro del lote (se queda la última versión de cada informe), y escritura en `eventos.live` con su conector de Kafka.
- **Python puro** (`observatorio/fusion/`): normalizar cada fuente y emparejar. Es la lógica delicada y se prueba con pytest sin levantar Spark.
- **Honestidad sobre el tamaño**: en directo son unos cientos de eventos al día; Spark está sobredimensionado para eso. Se justifica por el relleno (unos 200.000 informes de 2025–2026), por el objetivo docente (Big Data) y porque deja el camino abierto a más fuentes.

## Garantía de entrega de la fusión

Orden en cada lote: (1) leer estado y decidir, en una transacción de PostgreSQL abierta; (2) escribir los mensajes en `eventos.live` (`acks=all`); (3) `COMMIT` del estado; (4) Spark guarda el offset en el *checkpoint*.

| Fallo entre… | Qué pasa |
|---|---|
| 1 y 2 | Nada escrito. El lote se repite. |
| 2 y 3 | Mensajes en Kafka, estado sin guardar. El lote se repite y, como la decisión es determinista y el estado es el mismo, se escriben **los mismos** mensajes (mismo id y misma versión): el consumidor los descarta. |
| 3 y 4 | Estado guardado, offset no. El lote se repite; los informes ya están con la misma versión, no hay cambios y no se emite nada (los mensajes ya estaban en Kafka). |

- **Determinismo**: la versión del evento fusionado es `max(versión de sus informes, versión anterior + 1 ms)` y `ingested_at` es el máximo de los de sus informes: no depende del reloj del proceso.
- **Alternativa descartada**: escribir con un productor de `aiokafka` dentro del lote. Funciona igual, pero el conector de Kafka de Spark es la pieza que se quiere enseñar.

## Id canónico y eventos que ya existían

- **Decisión**: el id del primer informe; USGS tal cual (`us7000abcd`), EMSC con prefijo (`emsc-20261113_0000315`).
- **Por qué USGS sin prefijo**: la base ya tiene ~1.000 eventos con id USGS y el modo `replay` también los usa. Al arrancar, la fusión copia esos eventos a su estado (`fusion.informe`) con su id; si después llega su pareja de EMSC se une a ellos y no hay duplicado.
- **Alternativa descartada**: id derivado de un hash del contenido o del primer informe por hora: cambiaría al unirse otra fuente y rompería el upsert por id.

## Fuente principal

- **Decisión**: EMSC en Europa (lat 34–72, lon −25–45), USGS fuera. Son las redes que mejor conocen cada zona.
- **Alternativa**: la de magnitud más reciente o la de `auth` local de EMSC. Más fina, pero más difícil de explicar y de probar.

## Relleno

- **Volumen medido**: 2025 M ≥ 2,5: USGS 29.286, EMSC 79.758. 2026 hasta el 14-nov: USGS 25.533, EMSC unos 65.000. En total, unos 200.000 informes. Un mes de EMSC (≈ 10.000 eventos) se descarga en 1,4 s.
- **Ruta**: el relleno publica en los mismos topics por fuente; así pasa por la misma fusión que el directo. No hay un segundo camino a la base.
- **Partición**: USGS rechaza más de 20.000 (se parte por encima de 15.000); EMSC corta en ~10.000 (se parte por encima de 8.000). Se cuenta antes con `/count`.

## Imagen de Spark

- **Decisión**: imagen propia `python:3.12-slim-bookworm` + `openjdk-17-jre-headless` + `pyspark==4.2.1` (publicado el 2026-10-27) y el conector `org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.1`, descargado durante el *build*.
- **Razón**: PySpark 4.2 pide Python ≥ 3.11 y Java 17; así se reutiliza el mismo paquete `observatorio` y el arranque no descarga nada.
- **Alternativa**: la imagen oficial `apache/spark` (Python del sistema de Ubuntu, otra versión que el backend).
- **Coste**: unos 1–2 GB de RAM; modo local con 2 hilos.

## Comparación con 2025

- La base sigue siendo USGS M ≥ 4. En directo, el recuento M ≥ 4 de las últimas 24 h sale ahora de USGS ∪ EMSC fusionados, que para M ≥ 4 es casi lo mismo (97 %). Se documenta como limitación en la memoria.
