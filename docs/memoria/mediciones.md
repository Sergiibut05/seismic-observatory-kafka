# Mediciones de complejidad y memoria (feature 007)

- **Fecha de medición (UTC)**: 2026-11-08T14:12:01Z
- **Comando**: `python -m observatorio.mediciones --tamanos 1000,10000,100000 --repeticiones 5`
- **Tamaños de entrada**: 1.000, 10.000, 100.000; repeticiones por medida: 5 (mediana y máximo).
- **Datos**: SINTÉTICOS. Los generadores usan semilla fija; los ids llevan el prefijo `synthetic-medicion-` y `sintetico = true` en PostgreSQL. Nada de esto entra en el análisis real.

## Equipo

| Concepto | Valor |
| --- | --- |
| Sistema (contenedor) | Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.41 |
| CPU (modelo visible desde el contenedor) | AMD Ryzen 5 7600X 6-Core Processor |
| Núcleos visibles (`os.cpu_count`) | 12 |
| RAM visible (`/proc/meminfo`) | 15,15 GiB |
| Python | 3.12.16 |
| psycopg | 3.3.6 |
| shapely | 2.2.0 |
| GEOS | 3.14.1 |
| Disco del sistema de ficheros del contenedor | 1.006,9 GiB, libres 946,0 GiB |
| PostgreSQL | PostgreSQL 17.11 |
| PostgreSQL `shared_buffers` | 128MB |
| PostgreSQL `work_mem` | 4MB |
| PostgreSQL `max_parallel_workers_per_gather` | 2 |
| Catálogo de países | 242 polígonos; construir el `STRtree` y las áreas: 141,4 ms; RSS del proceso +20.120 KiB (aproximado, incluye GEOS) |

## Procedimiento

- Tiempo: `time.perf_counter` por repetición; se informan la **mediana** y el **máximo** en milisegundos.
- Memoria de Python: pico de `tracemalloc` (KiB) en una pasada aparte, porque `tracemalloc` ralentiza. Solo ve la memoria de Python: la de GEOS (el `STRtree`) queda fuera.
- Búsquedas: 200 ids elegidos al azar con semilla fija por cada medida.
- País: puntos uniformes sobre el globo (no siguen la sismicidad real: la mayoría cae en el mar y sale sin país). El recorrido secuencial prueba cada punto contra los polígonos del catálogo, ya preparados con `shapely.prepare`.
- PostgreSQL: esquema temporal `medicion` con una tabla de la forma de `live.evento_actual`; `EXPLAIN (ANALYZE, BUFFERS)` sin índices, después clave primaria e índice `(ocurrencia DESC, event_id)` y `ANALYZE`, y de nuevo `EXPLAIN`. El esquema se borra en un `finally`.
- Se mide mientras la pila sigue encendida: el productor, el consumidor y PostgreSQL comparten la máquina, así que los tiempos incluyen ese ruido.

## 1. Búsqueda de la última versión por id (datos SINTÉTICOS, medido el 2026-11-08T14:12:01Z)

| N | Operación | Repeticiones | Mediana (ms) | Máximo (ms) | Pico memoria (KiB) | Nota |
| --- | --- | --- | --- | --- | --- | --- |
| 1.000 | lista de tuplas: 200 búsquedas | 5 | 7,349 | 7,871 | 1,7 |  |
| 1.000 | lista de tuplas: construir (incluye mezclar) | 5 | 0,555 | 0,570 | 163,2 |  |
| 1.000 | diccionario: construir | 5 | 0,114 | 0,208 | 19,3 | el pico es el diccionario; las cadenas se comparten con la lista |
| 1.000 | diccionario: 200 búsquedas | 5 | 0,010 | 0,013 | 1,7 |  |
| 10.000 | lista de tuplas: 200 búsquedas | 5 | 80,383 | 81,285 | 1,7 |  |
| 10.000 | lista de tuplas: construir (incluye mezclar) | 5 | 6,447 | 6,683 | 1.607,8 |  |
| 10.000 | diccionario: construir | 5 | 1,201 | 1,931 | 152,3 | el pico es el diccionario; las cadenas se comparten con la lista |
| 10.000 | diccionario: 200 búsquedas | 5 | 0,012 | 0,016 | 1,7 |  |
| 100.000 | lista de tuplas: 200 búsquedas | 5 | 2.712,153 | 2.915,688 | 1,7 |  |
| 100.000 | lista de tuplas: construir (incluye mezclar) | 5 | 84,809 | 88,322 | 16.095,9 |  |
| 100.000 | diccionario: construir | 5 | 35,218 | 36,297 | 2.816,3 | el pico es el diccionario; las cadenas se comparten con la lista |
| 100.000 | diccionario: 200 búsquedas | 5 | 0,014 | 0,051 | 1,7 |  |

## 2. País de un punto (datos SINTÉTICOS, medido el 2026-11-08T14:12:01Z)

| N | Operación | Repeticiones | Mediana (ms) | Máximo (ms) | Pico memoria (KiB) | Nota |
| --- | --- | --- | --- | --- | --- | --- |
| 1.000 | secuencial (242 polígonos preparados) | 5 | 56,772 | 64,673 | 64,8 |  |
| 1.000 | STRtree (`IndicePaises.asignar`) | 5 | 16,543 | 17,291 | 111,7 |  |
| 10.000 | secuencial (242 polígonos preparados) | 5 | 534,152 | 560,722 | 631,5 |  |
| 10.000 | STRtree (`IndicePaises.asignar`) | 5 | 162,993 | 176,148 | 725,2 |  |
| 100.000 | secuencial (242 polígonos preparados) | 5 | 5.370,218 | 5.453,029 | 6.252,4 |  |
| 100.000 | STRtree (`IndicePaises.asignar`) | 5 | 1.631,234 | 1.906,465 | 6.346,1 |  |

Secuencial y `STRtree` asignan el mismo país a todos los puntos medidos: **sí**.

## 3. Agregación por hora UTC (datos SINTÉTICOS, medido el 2026-11-08T14:12:01Z)

| N | Operación | Repeticiones | Mediana (ms) | Máximo (ms) | Pico memoria (KiB) | Nota |
| --- | --- | --- | --- | --- | --- | --- |
| 1.000 | dict de contadores | 5 | 0,183 | 0,222 | 37,8 | memoria casi constante: una entrada por hora (≤ 720) |
| 1.000 | ordenar y agrupar | 5 | 0,447 | 0,477 | 46,3 |  |
| 10.000 | dict de contadores | 5 | 1,989 | 2,069 | 75,5 | memoria casi constante: una entrada por hora (≤ 720) |
| 10.000 | ordenar y agrupar | 5 | 3,077 | 3,209 | 154,2 |  |
| 100.000 | dict de contadores | 5 | 19,654 | 20,518 | 75,5 | memoria casi constante: una entrada por hora (≤ 720) |
| 100.000 | ordenar y agrupar | 5 | 34,852 | 41,716 | 1.171,8 |  |

## 4. PostgreSQL sin y con índice (datos SINTÉTICOS `synthetic-medicion-`, medido el 2026-11-08T14:12:01Z)

| N | Consulta | Índice | Mediana (ms) | Máximo (ms) | Buffers (último plan) |
| --- | --- | --- | --- | --- | --- |
| 1.000 | búsqueda por event_id | sin índice | 0,074 | 0,087 | shared hit=22 |
| 1.000 | lista paginada (ORDER BY ocurrencia DESC LIMIT 100) | sin índice | 0,193 | 0,223 | shared hit=22 |
| 1.000 | ventana horaria de 24 h (GROUP BY hora) | sin índice | 0,094 | 0,154 | shared hit=22 |
| 1.000 | búsqueda por event_id | con índice | 0,024 | 0,029 | shared hit=3 |
| 1.000 | lista paginada (ORDER BY ocurrencia DESC LIMIT 100) | con índice | 0,047 | 0,052 | shared hit=102 |
| 1.000 | ventana horaria de 24 h (GROUP BY hora) | con índice | 0,074 | 0,096 | shared hit=6 |
| 10.000 | búsqueda por event_id | sin índice | 0,688 | 0,749 | shared hit=213 |
| 10.000 | lista paginada (ORDER BY ocurrencia DESC LIMIT 100) | sin índice | 1,344 | 1,501 | shared hit=213 |
| 10.000 | ventana horaria de 24 h (GROUP BY hora) | sin índice | 0,600 | 0,751 | shared hit=213 |
| 10.000 | búsqueda por event_id | con índice | 0,029 | 0,117 | shared hit=3 |
| 10.000 | lista paginada (ORDER BY ocurrencia DESC LIMIT 100) | con índice | 0,054 | 0,125 | shared hit=102 |
| 10.000 | ventana horaria de 24 h (GROUP BY hora) | con índice | 0,184 | 0,319 | shared hit=41 |
| 100.000 | búsqueda por event_id | sin índice | 5,966 | 7,071 | shared hit=2213 |
| 100.000 | lista paginada (ORDER BY ocurrencia DESC LIMIT 100) | sin índice | 12,484 | 13,268 | shared hit=2258 |
| 100.000 | ventana horaria de 24 h (GROUP BY hora) | sin índice | 7,888 | 8,681 | shared hit=2213 |
| 100.000 | búsqueda por event_id | con índice | 0,022 | 0,039 | shared hit=4 |
| 100.000 | lista paginada (ORDER BY ocurrencia DESC LIMIT 100) | con índice | 0,050 | 0,152 | shared hit=103 |
| 100.000 | ventana horaria de 24 h (GROUP BY hora) | con índice | 1,602 | 2,186 | shared hit=397 |

### Tamaño de las relaciones (`pg_total_relation_size`)

| N | Sin índices (bytes) | Tabla (bytes) | Índices (bytes) | Total con índices (bytes) | PK (bytes) | Índice ocurrencia (bytes) |
| --- | --- | --- | --- | --- | --- | --- |
| 1.000 | 212.992 | 180.224 | 131.072 | 344.064 | 57.344 | 73.728 |
| 10.000 | 1.777.664 | 1.744.896 | 942.080 | 2.719.744 | 425.984 | 516.096 |
| 100.000 | 18.161.664 | 18.128.896 | 10.690.560 | 28.852.224 | 4.907.008 | 5.783.552 |

### Planes (`EXPLAIN (ANALYZE, BUFFERS)`, último plan de cada serie)

#### N = 1.000 · búsqueda por event_id · sin índice

```text
Seq Scan on evento  (cost=0.00..34.50 rows=1 width=162) (actual time=0.028..0.054 rows=1 loops=1)
  Filter: (event_id = 'synthetic-medicion-500'::text)
  Rows Removed by Filter: 999
  Buffers: shared hit=22
Planning Time: 0.014 ms
Execution Time: 0.057 ms
```

#### N = 1.000 · lista paginada (ORDER BY ocurrencia DESC LIMIT 100) · sin índice

```text
Limit  (cost=70.22..70.47 rows=100 width=38) (actual time=0.196..0.204 rows=100 loops=1)
  Buffers: shared hit=22
  ->  Sort  (cost=70.22..72.72 rows=1000 width=38) (actual time=0.195..0.199 rows=100 loops=1)
        Sort Key: ocurrencia DESC, event_id
        Sort Method: top-N heapsort  Memory: 39kB
        Buffers: shared hit=22
        ->  Seq Scan on evento  (cost=0.00..32.00 rows=1000 width=38) (actual time=0.003..0.082 rows=1000 loops=1)
              Buffers: shared hit=22
Planning Time: 0.023 ms
Execution Time: 0.218 ms
```

#### N = 1.000 · ventana horaria de 24 h (GROUP BY hora) · sin índice

```text
GroupAggregate  (cost=37.91..38.57 rows=33 width=16) (actual time=0.073..0.081 rows=24 loops=1)
  Group Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
  Buffers: shared hit=22
  ->  Sort  (cost=37.91..38.00 rows=33 width=8) (actual time=0.071..0.073 rows=32 loops=1)
        Sort Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=22
        ->  Seq Scan on evento  (cost=0.00..37.08 rows=33 width=8) (actual time=0.011..0.063 rows=32 loops=1)
              Filter: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
              Rows Removed by Filter: 968
              Buffers: shared hit=22
Planning Time: 0.020 ms
Execution Time: 0.093 ms
```

#### N = 1.000 · búsqueda por event_id · con índice

```text
Index Scan using evento_pk on evento  (cost=0.28..8.29 rows=1 width=162) (actual time=0.012..0.013 rows=1 loops=1)
  Index Cond: (event_id = 'synthetic-medicion-500'::text)
  Buffers: shared hit=3
Planning Time: 0.026 ms
Execution Time: 0.024 ms
```

#### N = 1.000 · lista paginada (ORDER BY ocurrencia DESC LIMIT 100) · con índice

```text
Limit  (cost=0.28..13.93 rows=100 width=38) (actual time=0.011..0.031 rows=100 loops=1)
  Buffers: shared hit=102
  ->  Index Scan using evento_ocurrencia_idx on evento  (cost=0.28..136.87 rows=1000 width=38) (actual time=0.011..0.027 rows=100 loops=1)
        Buffers: shared hit=102
Planning Time: 0.033 ms
Execution Time: 0.043 ms
```

#### N = 1.000 · ventana horaria de 24 h (GROUP BY hora) · con índice

```text
GroupAggregate  (cost=29.05..29.71 rows=33 width=16) (actual time=0.035..0.043 rows=24 loops=1)
  Group Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
  Buffers: shared hit=6
  ->  Sort  (cost=29.05..29.13 rows=33 width=8) (actual time=0.034..0.035 rows=32 loops=1)
        Sort Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=6
        ->  Bitmap Heap Scan on evento  (cost=4.61..28.22 rows=33 width=8) (actual time=0.016..0.025 rows=32 loops=1)
              Recheck Cond: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
              Heap Blocks: exact=3
              Buffers: shared hit=6
              ->  Bitmap Index Scan on evento_ocurrencia_idx  (cost=0.00..4.61 rows=33 width=0) (actual time=0.011..0.011 rows=32 loops=1)
                    Index Cond: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
                    Buffers: shared hit=3
Planning Time: 0.033 ms
Execution Time: 0.072 ms
```

#### N = 10.000 · búsqueda por event_id · sin índice

```text
Seq Scan on evento  (cost=0.00..338.00 rows=1 width=163) (actual time=0.260..0.523 rows=1 loops=1)
  Filter: (event_id = 'synthetic-medicion-5000'::text)
  Rows Removed by Filter: 9999
  Buffers: shared hit=213
Planning Time: 0.020 ms
Execution Time: 0.527 ms
```

#### N = 10.000 · lista paginada (ORDER BY ocurrencia DESC LIMIT 100) · sin índice

```text
Limit  (cost=695.19..695.44 rows=100 width=39) (actual time=1.480..1.487 rows=100 loops=1)
  Buffers: shared hit=213
  ->  Sort  (cost=695.19..720.19 rows=10000 width=39) (actual time=1.479..1.482 rows=100 loops=1)
        Sort Key: ocurrencia DESC, event_id
        Sort Method: top-N heapsort  Memory: 39kB
        Buffers: shared hit=213
        ->  Seq Scan on evento  (cost=0.00..313.00 rows=10000 width=39) (actual time=0.017..0.737 rows=10000 loops=1)
              Buffers: shared hit=213
Planning Time: 0.016 ms
Execution Time: 1.501 ms
```

#### N = 10.000 · ventana horaria de 24 h (GROUP BY hora) · sin índice

```text
GroupAggregate  (cost=378.04..384.80 rows=338 width=16) (actual time=0.552..0.579 rows=24 loops=1)
  Group Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
  Buffers: shared hit=213
  ->  Sort  (cost=378.04..378.89 rows=338 width=8) (actual time=0.550..0.558 rows=337 loops=1)
        Sort Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=213
        ->  Seq Scan on evento  (cost=0.00..363.85 rows=338 width=8) (actual time=0.011..0.531 rows=337 loops=1)
              Filter: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
              Rows Removed by Filter: 9663
              Buffers: shared hit=213
Planning Time: 0.018 ms
Execution Time: 0.592 ms
```

#### N = 10.000 · búsqueda por event_id · con índice

```text
Index Scan using evento_pk on evento  (cost=0.29..8.30 rows=1 width=163) (actual time=0.012..0.012 rows=1 loops=1)
  Index Cond: (event_id = 'synthetic-medicion-5000'::text)
  Buffers: shared hit=3
Planning Time: 0.021 ms
Execution Time: 0.040 ms
```

#### N = 10.000 · lista paginada (ORDER BY ocurrencia DESC LIMIT 100) · con índice

```text
Limit  (cost=0.29..12.82 rows=100 width=39) (actual time=0.011..0.037 rows=100 loops=1)
  Buffers: shared hit=102
  ->  Index Scan using evento_ocurrencia_idx on evento  (cost=0.29..1254.26 rows=10000 width=39) (actual time=0.011..0.032 rows=100 loops=1)
        Buffers: shared hit=102
Planning Time: 0.018 ms
Execution Time: 0.048 ms
```

#### N = 10.000 · ventana horaria de 24 h (GROUP BY hora) · con índice

```text
GroupAggregate  (cost=257.76..264.52 rows=338 width=16) (actual time=0.120..0.147 rows=24 loops=1)
  Group Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
  Buffers: shared hit=41
  ->  Sort  (cost=257.76..258.61 rows=338 width=8) (actual time=0.117..0.126 rows=337 loops=1)
        Sort Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=41
        ->  Bitmap Heap Scan on evento  (cost=15.75..243.56 rows=338 width=8) (actual time=0.021..0.099 rows=337 loops=1)
              Recheck Cond: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
              Heap Blocks: exact=37
              Buffers: shared hit=41
              ->  Bitmap Index Scan on evento_ocurrencia_idx  (cost=0.00..15.66 rows=338 width=0) (actual time=0.016..0.016 rows=337 loops=1)
                    Index Cond: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
                    Buffers: shared hit=4
Planning Time: 0.030 ms
Execution Time: 0.174 ms
```

#### N = 100.000 · búsqueda por event_id · sin índice

```text
Seq Scan on evento  (cost=0.00..3463.00 rows=1 width=164) (actual time=3.480..7.065 rows=1 loops=1)
  Filter: (event_id = 'synthetic-medicion-50000'::text)
  Rows Removed by Filter: 99999
  Buffers: shared hit=2213
Planning Time: 0.030 ms
Execution Time: 7.071 ms
```

#### N = 100.000 · lista paginada (ORDER BY ocurrencia DESC LIMIT 100) · sin índice

```text
Limit  (cost=6049.46..6060.96 rows=100 width=40) (actual time=10.421..12.225 rows=100 loops=1)
  Buffers: shared hit=2258
  ->  Gather Merge  (cost=6049.46..12814.22 rows=58824 width=40) (actual time=10.420..12.218 rows=100 loops=1)
        Workers Planned: 1
        Workers Launched: 1
        Buffers: shared hit=2258
        ->  Sort  (cost=5049.45..5196.51 rows=58824 width=40) (actual time=8.862..8.865 rows=82 loops=2)
              Sort Key: ocurrencia DESC, event_id
              Sort Method: top-N heapsort  Memory: 39kB
              Buffers: shared hit=2258
              Worker 0:  Sort Method: top-N heapsort  Memory: 39kB
              ->  Parallel Seq Scan on evento  (cost=0.00..2801.24 rows=58824 width=40) (actual time=0.006..5.157 rows=50000 loops=2)
                    Buffers: shared hit=2213
Planning Time: 0.034 ms
Execution Time: 12.245 ms
```

#### N = 100.000 · ventana horaria de 24 h (GROUP BY hora) · sin índice

```text
GroupAggregate  (cost=3905.94..3969.54 rows=3180 width=16) (actual time=7.695..7.933 rows=24 loops=1)
  Group Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
  Buffers: shared hit=2213
  ->  Sort  (cost=3905.94..3913.89 rows=3180 width=8) (actual time=7.680..7.763 rows=3337 loops=1)
        Sort Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
        Sort Method: quicksort  Memory: 97kB
        Buffers: shared hit=2213
        ->  Seq Scan on evento  (cost=0.00..3720.95 rows=3180 width=8) (actual time=0.016..7.422 rows=3337 loops=1)
              Filter: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
              Rows Removed by Filter: 96663
              Buffers: shared hit=2213
Planning Time: 0.032 ms
Execution Time: 7.954 ms
```

#### N = 100.000 · búsqueda por event_id · con índice

```text
Index Scan using evento_pk on evento  (cost=0.42..8.44 rows=1 width=164) (actual time=0.010..0.011 rows=1 loops=1)
  Index Cond: (event_id = 'synthetic-medicion-50000'::text)
  Buffers: shared hit=4
Planning Time: 0.018 ms
Execution Time: 0.020 ms
```

#### N = 100.000 · lista paginada (ORDER BY ocurrencia DESC LIMIT 100) · con índice

```text
Limit  (cost=0.42..13.59 rows=100 width=40) (actual time=0.018..0.063 rows=100 loops=1)
  Buffers: shared hit=103
  ->  Index Scan using evento_ocurrencia_idx on evento  (cost=0.42..13176.33 rows=100000 width=40) (actual time=0.018..0.056 rows=100 loops=1)
        Buffers: shared hit=103
Planning Time: 0.033 ms
Execution Time: 0.082 ms
```

#### N = 100.000 · ventana horaria de 24 h (GROUP BY hora) · con índice

```text
GroupAggregate  (cost=2699.62..2765.04 rows=3271 width=16) (actual time=1.175..1.416 rows=24 loops=1)
  Group Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
  Buffers: shared hit=397
  ->  Sort  (cost=2699.62..2707.80 rows=3271 width=8) (actual time=1.163..1.246 rows=3337 loops=1)
        Sort Key: (date_trunc('hour'::text, ocurrencia, 'UTC'::text))
        Sort Method: quicksort  Memory: 97kB
        Buffers: shared hit=397
        ->  Bitmap Heap Scan on evento  (cost=129.95..2508.67 rows=3271 width=8) (actual time=0.142..0.980 rows=3337 loops=1)
              Recheck Cond: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
              Heap Blocks: exact=371
              Buffers: shared hit=397
              ->  Bitmap Index Scan on evento_ocurrencia_idx  (cost=0.00..129.13 rows=3271 width=0) (actual time=0.109..0.109 rows=3337 loops=1)
                    Index Cond: ((ocurrencia >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND (ocurrencia < '2026-10-16 00:00:00+00'::timestamp with time zone))
                    Buffers: shared hit=26
Planning Time: 0.031 ms
Execution Time: 1.447 ms
```

## 5. Extrapolación a 100.000.000 de registros (EXTRAPOLACIÓN, no medida)

Cada estimación parte de la mediana del mayor tamaño medido y de la complejidad teórica de la operación: lineal, logarítmica o constante. No tiene en cuenta que con esa escala los datos dejan de caber en RAM ni la caché; es un orden de magnitud, no un resultado.

| Operación | Modelo | Estimación (NO medida) |
| --- | --- | --- |
| version: lista de tuplas: 200 búsquedas | O(n) | tiempo ≈ 45,2 min |
| version: lista de tuplas: construir (incluye mezclar) | O(n) | tiempo ≈ 84,8 s; memoria ≈ 15,35 GiB |
| version: diccionario: construir | O(n) | tiempo ≈ 35,2 s; memoria ≈ 2,69 GiB |
| version: diccionario: 200 búsquedas | O(1) | tiempo ≈ 0,01 ms |
| pais: secuencial (242 polígonos preparados) | O(n) | tiempo ≈ 89,5 min; memoria ≈ 5,96 GiB |
| pais: STRtree (`IndicePaises.asignar`) | O(n) | tiempo ≈ 27,2 min; memoria ≈ 6,05 GiB |
| hora: dict de contadores | O(n) | tiempo ≈ 19,7 s |
| hora: ordenar y agrupar | O(n log n) | tiempo ≈ 55,8 s; memoria ≈ 1,12 GiB |
| postgres: búsqueda por event_id, sin índice | O(n) | tiempo ≈ 6,0 s |
| postgres: lista paginada (ORDER BY ocurrencia DESC LIMIT 100), sin índice | O(n) | tiempo ≈ 12,5 s |
| postgres: ventana horaria de 24 h (GROUP BY hora), sin índice | O(n) | tiempo ≈ 7,9 s |
| postgres: búsqueda por event_id, con índice | O(log n) | tiempo ≈ 0,04 ms |
| postgres: lista paginada (ORDER BY ocurrencia DESC LIMIT 100), con índice | O(1) | tiempo ≈ 0,05 ms |
| postgres: ventana horaria de 24 h (GROUP BY hora), con índice | O(n) | tiempo ≈ 1,6 s |
| postgres: tamaño de la tabla | O(n) | sin índices ≈ 16,91 GiB; con índices ≈ 26,87 GiB |

## 6. Garantía: recuentos antes y después

Solo se cuentan filas reales. `live` puede crecer durante la medición porque la ingesta sigue en marcha (se tolera crecer, nunca decrecer); `replay` e `historico` tienen que quedar iguales.

| Recuento | Antes | Después |
| --- | --- | --- |
| live.evento_actual (reales) | 477 | 478 |
| live.versiones_evento (reales) | 521 | 523 |
| live.* con prefijo synthetic-medicion- | 0 | 0 |
| replay.evento_actual (reales) | 40 | 40 |
| replay.versiones_evento (reales) | 41 | 41 |
| historico.evento_2025 | 18.302 | 18.302 |

Esquemas `medicion` tras la medición: 0 (esperado: 0).

Garantía cumplida: nada fuera del esquema `medicion` cambió de forma inadmisible.

