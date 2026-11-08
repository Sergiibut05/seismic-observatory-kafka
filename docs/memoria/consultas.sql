-- Consultas de la memoria (feature 007). Cada cifra de docs/MEMORIA.md sale de una de estas consultas (Qnn).
--
-- Cómo ejecutarlas (PowerShell, desde la raíz; la pila en marcha y psql solo en lectura):
--   $OutputEncoding = [Text.UTF8Encoding]::new($false); [Console]::OutputEncoding = [Text.Encoding]::UTF8
--   Get-Content -Raw -Encoding utf8 docs\memoria\consultas.sql | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f -'
--
-- Fecha de medición de todas las cifras: 2026-11-08 (UTC; la hora exacta va en docs/memoria/consultas.resultado.txt).
-- Solo lectura: no hay INSERT, UPDATE, DELETE ni DDL. Los EXPLAIN con ANALYZE ejecutan solo SELECT.
-- Datos reales: toda consulta de calidad y de análisis excluye los casos sintéticos con `NOT sintetico`
-- (live y replay) o por el prefijo `synthetic-` de la clave (cuarentena, que no tiene esa columna).
-- `historico` solo contiene datos reales de USGS y no tiene la columna.

\set ON_ERROR_STOP on
\pset null '(nulo)'
\pset footer off
\timing off

\echo '== instante de la ejecución =='
SELECT now() AT TIME ZONE 'UTC' AS ejecutado_utc, version() AS postgresql;

-- ============================================================================================
-- A. DICCIONARIO Y MODELO
-- ============================================================================================

\echo
\echo '== Q01 · columnas por tabla (live, replay, ingesta, historico); la última fila es el total =='
-- Mide: cuántas columnas hay en el modelo. El diccionario de la memoria debe sumar lo mismo (AC-2). 2026-11-08
SELECT coalesce(table_schema, 'TOTAL') AS esquema, coalesce(table_name, '') AS tabla, count(*) AS columnas
FROM information_schema.columns
WHERE table_schema IN ('live', 'replay', 'ingesta', 'historico')
GROUP BY ROLLUP (table_schema, table_name)
ORDER BY table_schema NULLS LAST, table_name NULLS LAST;

\echo
\echo '== Q02 · definición de cada columna (tipo, nulabilidad, valor por defecto) =='
-- Mide: la fuente del diccionario de datos (tipo y nulabilidad). 2026-11-08
SELECT table_schema AS esquema, table_name AS tabla, ordinal_position AS n, column_name AS columna,
       data_type AS tipo, is_nullable AS admite_nulo, column_default AS por_defecto
FROM information_schema.columns
WHERE table_schema IN ('live', 'replay', 'ingesta', 'historico')
ORDER BY table_schema, table_name, ordinal_position;

\echo
\echo '== Q03 · live y replay tienen las mismas columnas, tipos y nulabilidad (0 y 0 = idénticas) =='
-- Mide: por qué el diccionario describe live y replay una sola vez. 2026-11-08
WITH l AS (SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'live'),
     r AS (SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'replay')
SELECT (SELECT count(*) FROM (SELECT * FROM l EXCEPT SELECT * FROM r) x) AS columnas_solo_en_live,
       (SELECT count(*) FROM (SELECT * FROM r EXCEPT SELECT * FROM l) x) AS columnas_solo_en_replay,
       (SELECT count(*) FROM l) AS columnas_en_live;

\echo
\echo '== Q04a · restricciones (PK, FK, CHECK, UNIQUE) =='
-- Mide: claves y restricciones del modelo físico. 2026-11-08
SELECT n.nspname || '.' || c.relname AS tabla, con.conname AS restriccion, con.contype AS tipo,
       pg_get_constraintdef(con.oid) AS definicion
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('live', 'replay', 'ingesta', 'historico') AND con.contype IN ('p', 'f', 'u', 'c')
ORDER BY 1, 2;

\echo
\echo '== Q04b · índices =='
-- Mide: los índices existentes (cada uno se justifica con un EXPLAIN en Q30 y en docs/memoria/mediciones.md). 2026-11-08
SELECT schemaname || '.' || tablename AS tabla, indexname AS indice, indexdef AS definicion
FROM pg_indexes
WHERE schemaname IN ('live', 'replay', 'ingesta', 'historico')
ORDER BY 1, 2;

\echo
\echo '== Q04c · cuántas veces se ha usado cada índice desde que PostgreSQL acumula estadísticas =='
-- Mide: idx_scan de pg_stat_user_indexes (recorridos por el índice); 0 = ninguna consulta lo ha usado. 2026-11-08
SELECT s.schemaname || '.' || s.relname AS tabla, s.indexrelname AS indice, s.idx_scan AS usos,
       pg_relation_size(s.indexrelid) AS bytes_indice
FROM pg_stat_user_indexes s
WHERE s.schemaname IN ('live', 'replay', 'ingesta', 'historico')
ORDER BY s.schemaname, s.relname, s.indexrelname;

\echo
\echo '== Q05 · tamaño de cada tabla (pg_total_relation_size) =='
-- Mide: bytes de tabla, índices y total; entrada del apartado de costes de almacenamiento. 2026-11-08
SELECT n.nspname || '.' || c.relname AS tabla,
       pg_relation_size(c.oid) AS bytes_tabla,
       pg_indexes_size(c.oid) AS bytes_indices,
       pg_total_relation_size(c.oid) AS bytes_total
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname IN ('live', 'replay', 'ingesta', 'historico')
ORDER BY bytes_total DESC, tabla;

\echo
\echo '== Q05b · tamaño total de la base de datos (tablas, índices, catálogo del sistema y WAL de la base) =='
-- Mide: bytes de la base `observatorio` (insumo del coste de almacenamiento) y suma de las tablas de Q05. 2026-11-08
SELECT pg_database_size(current_database()) AS bytes_base,
       (SELECT sum(pg_total_relation_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('live', 'replay', 'ingesta', 'historico') AND c.relkind = 'r') AS bytes_tablas_de_q05;

\echo
\echo '== Q06 · filas por tabla (en live y replay, separadas reales y sintéticas) =='
-- Mide: volumen real de cada tabla. Las sintéticas son los casos de prueba de la feature 007. 2026-11-08
SELECT 'live.evento_actual' AS tabla, count(*) AS filas, count(*) FILTER (WHERE NOT sintetico) AS reales, count(*) FILTER (WHERE sintetico) AS sinteticas FROM live.evento_actual
UNION ALL SELECT 'live.versiones_evento', count(*), count(*) FILTER (WHERE NOT sintetico), count(*) FILTER (WHERE sintetico) FROM live.versiones_evento
UNION ALL SELECT 'replay.evento_actual', count(*), count(*) FILTER (WHERE NOT sintetico), count(*) FILTER (WHERE sintetico) FROM replay.evento_actual
UNION ALL SELECT 'replay.versiones_evento', count(*), count(*) FILTER (WHERE NOT sintetico), count(*) FILTER (WHERE sintetico) FROM replay.versiones_evento
UNION ALL SELECT 'historico.evento_2025', count(*), count(*), 0 FROM historico.evento_2025
UNION ALL SELECT 'ingesta.pais', count(*), count(*), 0 FROM ingesta.pais
UNION ALL SELECT 'ingesta.consultas', count(*), count(*), 0 FROM ingesta.consultas
UNION ALL SELECT 'ingesta.publicadas', count(*), count(*) FILTER (WHERE event_id NOT LIKE 'synthetic-%'), count(*) FILTER (WHERE event_id LIKE 'synthetic-%') FROM ingesta.publicadas
UNION ALL SELECT 'ingesta.exclusiones', count(*), count(*), 0 FROM ingesta.exclusiones
-- Cuarentena no tiene columna `sintetico`: «reales» = ni prefijo `synthetic-` ni las claves de las pruebas dañadas de 001.
UNION ALL SELECT 'ingesta.cuarentena (todas)', count(*),
       count(*) FILTER (WHERE substring(clave FROM 1 FOR 10) <> 'synthetic-'::bytea AND clave NOT IN ('k1'::bytea, 'otra'::bytea, 'us2'::bytea, 'us3'::bytea)),
       count(*) FILTER (WHERE substring(clave FROM 1 FOR 10) = 'synthetic-'::bytea) FROM ingesta.cuarentena
UNION ALL SELECT 'ingesta.cuarentena: pruebas dañadas de 001 sin prefijo', count(*), 0, 0
       FROM ingesta.cuarentena WHERE clave IN ('k1'::bytea, 'otra'::bytea, 'us2'::bytea, 'us3'::bytea)
UNION ALL SELECT 'ingesta.version_esquema', count(*), count(*), 0 FROM ingesta.version_esquema;

-- ============================================================================================
-- B. REGISTRO DE CONSULTAS Y PROCEDENCIA
-- ============================================================================================

\echo
\echo '== Q07 · resumen de ingesta.consultas (feed USGS all_day) =='
-- Mide: consultas, HTTP, errores, copias nuevas, bytes y reparto publicados/omitidos/excluidos. 2026-11-08
SELECT count(*) AS consultas,
       min(acabada_en) AS primera, max(acabada_en) AS ultima,
       count(*) FILTER (WHERE http_status = 200) AS http_200,
       count(*) FILTER (WHERE http_status IS DISTINCT FROM 200) AS http_otro,
       count(*) FILTER (WHERE error IS NOT NULL) AS con_error,
       count(*) FILTER (WHERE copia_nueva) AS copias_nuevas,
       round(100.0 * count(*) FILTER (WHERE copia_nueva) / count(*), 1) AS pct_copia_nueva,
       sum(bytes) AS bytes_recibidos, round(avg(bytes)) AS bytes_medios,
       sum(features) AS features_recibidas, sum(publicados) AS publicados, sum(omitidos) AS omitidos, sum(excluidos) AS excluidos
FROM ingesta.consultas;

\echo
\echo '== Q08 · consultas por estado HTTP y error =='
-- Mide: errores del feed registrados (http_status y error). 2026-11-08
SELECT http_status, error, count(*) AS consultas FROM ingesta.consultas GROUP BY 1, 2 ORDER BY 3 DESC;

\echo
\echo '== Q09a · huecos entre consultas de más de 10 minutos =='
-- Mide: el hueco real en que el sistema estuvo apagado (2-8 de noviembre de 2026). 2026-11-08
WITH c AS (SELECT id, acabada_en, lag(acabada_en) OVER (ORDER BY id) AS anterior FROM ingesta.consultas)
SELECT id AS consulta_id, anterior AS ultima_consulta_antes, acabada_en AS primera_consulta_despues,
       acabada_en - anterior AS hueco
FROM c WHERE acabada_en - anterior > interval '10 minutes' ORDER BY id;

\echo
\echo '== Q09b · cobertura de consultas por día UTC (1.440 esperadas con una por minuto) =='
-- Mide: cuántas consultas hay cada día y qué porcentaje del ideal; los días con 0 son el hueco. 2026-11-08
SELECT d::date AS dia, count(c.id) AS consultas, round(100.0 * count(c.id) / 1440, 1) AS pct_de_1440
FROM generate_series((SELECT date_trunc('day', min(acabada_en)) FROM ingesta.consultas),
                     (SELECT date_trunc('day', max(acabada_en)) FROM ingesta.consultas), interval '1 day') AS d
LEFT JOIN ingesta.consultas c ON date_trunc('day', c.acabada_en) = d
GROUP BY d ORDER BY d;

\echo
\echo '== Q10 · terremotos reales del estado actual por día de ocurrencia (UTC) =='
-- Mide: el mismo hueco visto en los datos: sin consultas no hay eventos de esos días (el feed solo mira 24 h atrás). 2026-11-08
SELECT d::date AS dia, count(e.event_id) AS eventos_reales
FROM generate_series((SELECT date_trunc('day', min(ocurrencia)) FROM live.evento_actual WHERE NOT sintetico),
                     (SELECT date_trunc('day', max(ocurrencia)) FROM live.evento_actual WHERE NOT sintetico), interval '1 day') AS d
LEFT JOIN live.evento_actual e ON NOT e.sintetico AND date_trunc('day', e.ocurrencia) = d
GROUP BY d ORDER BY d;

\echo
\echo '== Q10b · saltos de más de una hora entre ocurrencias consecutivas de terremotos reales (el hueco de datos) =='
-- Mide: el intervalo de tiempo de ocurrencia sin ningún evento real; es lo que habría que recuperar por FDSN. 2026-11-08
SELECT anterior AS ultima_ocurrencia_antes, siguiente AS primera_ocurrencia_despues, siguiente - anterior AS salto
FROM (SELECT ocurrencia AS siguiente, lag(ocurrencia) OVER (ORDER BY ocurrencia) AS anterior
      FROM live.evento_actual WHERE NOT sintetico) t
WHERE siguiente - anterior > interval '1 hour' ORDER BY salto DESC LIMIT 5;

\echo
\echo '== Q11 · histórico 2025: filas frente a las 18.302 del manifiesto =='
-- Mide: 18.302 = campo `eventos` de data/historico/2025/manifest.json (se lee con PowerShell, ver la memoria). 2026-11-08
SELECT count(*) AS filas, count(DISTINCT event_id) AS ids_distintos, 18302 AS eventos_en_manifest,
       count(*) = 18302 AS coincide, min(ocurrencia) AS primera_ocurrencia, max(ocurrencia) AS ultima_ocurrencia,
       min(cargado_en) AS cargado_desde, max(cargado_en) AS cargado_hasta
FROM historico.evento_2025;

\echo
\echo '== Q12 · cada versión con acuse (ingesta.publicadas) tiene su versión persistida y al revés =='
-- Mide: coherencia entre «publicado» (productor) y «persistido» (consumidor) para eventos reales. 2026-11-08
SELECT (SELECT count(*) FROM ingesta.publicadas WHERE event_id NOT LIKE 'synthetic-%') AS publicadas_reales,
       (SELECT count(*) FROM live.versiones_evento WHERE NOT sintetico) AS versiones_reales,
       (SELECT count(*) FROM ingesta.publicadas p
         WHERE p.event_id NOT LIKE 'synthetic-%'
           AND NOT EXISTS (SELECT 1 FROM live.versiones_evento v
                           WHERE v.event_id = p.event_id AND v.updated = timestamptz 'epoch' + p.updated_ms * interval '1 millisecond')) AS publicadas_sin_persistir,
       (SELECT count(*) FROM live.versiones_evento v
         WHERE NOT v.sintetico
           AND NOT EXISTS (SELECT 1 FROM ingesta.publicadas p
                           WHERE p.event_id = v.event_id AND v.updated = timestamptz 'epoch' + p.updated_ms * interval '1 millisecond')) AS persistidas_sin_acuse;

\echo
\echo '== Q13 · frecuencia del feed: intervalo entre consultas y fracción con copia nueva =='
-- Mide: la cadencia real (objetivo 60 s) sin contar los huecos de más de 10 minutos. 2026-11-08
WITH d AS (SELECT acabada_en - lag(acabada_en) OVER (ORDER BY id) AS intervalo FROM ingesta.consultas)
SELECT count(*) AS intervalos,
       round(extract(epoch FROM percentile_cont(0.5) WITHIN GROUP (ORDER BY intervalo))::numeric, 1) AS mediana_s,
       round(extract(epoch FROM percentile_cont(0.95) WITHIN GROUP (ORDER BY intervalo))::numeric, 1) AS p95_s,
       round(extract(epoch FROM max(intervalo))::numeric, 1) AS maximo_s
FROM d WHERE intervalo < interval '10 minutes';

\echo
\echo '== Q14 · replay: eventos reproducidos y sus tiempos original y de reproducción =='
-- Mide: los 40 eventos de la reproducción histórica (+1 revisión en versiones). 2026-11-08
SELECT count(*) AS eventos, (SELECT count(*) FROM replay.versiones_evento) AS versiones,
       min(ocurrencia) AS ocurrencia_primera, max(ocurrencia) AS ocurrencia_ultima,
       min(ingested_at) AS reproducido_desde, max(ingested_at) AS reproducido_hasta
FROM replay.evento_actual WHERE NOT sintetico;

-- ============================================================================================
-- C. CALIDAD: seis dimensiones sobre datos REALES (NOT sintetico)
-- ============================================================================================

\echo
\echo '== Q15 · COMPLETITUD, antes: disponibilidad de cada campo en el GeoJSON original (versiones reales) =='
-- Mide: porcentaje de versiones con valor (no ausente ni null) en cada campo de `properties` y en la profundidad. 2026-11-08
WITH v AS (SELECT original -> 'event' AS e FROM live.versiones_evento WHERE NOT sintetico),
     t AS (SELECT count(*) AS total FROM v)
SELECT p.k AS campo, count(*) FILTER (WHERE jsonb_typeof(p.val) <> 'null') AS con_valor, t.total,
       round(100.0 * count(*) FILTER (WHERE jsonb_typeof(p.val) <> 'null') / t.total, 2) AS pct_disponible
FROM v CROSS JOIN t CROSS JOIN LATERAL jsonb_each(v.e -> 'properties') AS p(k, val)
GROUP BY p.k, t.total
UNION ALL
SELECT 'geometry.coordinates[2] (profundidad)', count(*) FILTER (WHERE jsonb_typeof(e -> 'geometry' -> 'coordinates' -> 2) = 'number'), t.total,
       round(100.0 * count(*) FILTER (WHERE jsonb_typeof(e -> 'geometry' -> 'coordinates' -> 2) = 'number') / t.total, 2)
FROM v CROSS JOIN t GROUP BY t.total
ORDER BY pct_disponible DESC, campo;

\echo
\echo '== Q15b · COMPLETITUD: ejemplos de eventos reales con campos opcionales presentes (solo viven en `original`) =='
-- Mide: registros de ejemplo de los campos opcionales (alert, mmi, felt, cdi), que no se promueven a columna. 2026-11-08
SELECT event_id, updated, original -> 'event' -> 'properties' ->> 'mag' AS mag,
       original -> 'event' -> 'properties' ->> 'felt' AS felt, original -> 'event' -> 'properties' ->> 'cdi' AS cdi,
       original -> 'event' -> 'properties' ->> 'mmi' AS mmi, original -> 'event' -> 'properties' ->> 'alert' AS alert
FROM live.versiones_evento
WHERE NOT sintetico AND jsonb_typeof(original -> 'event' -> 'properties' -> 'alert') = 'string'
ORDER BY updated DESC LIMIT 3;

\echo
\echo '== Q16 · COMPLETITUD, después: nulos de magnitud, profundidad y país en las tablas de estado =='
-- Mide: nulos conservados tras la transformación (magnitud y profundidad nunca se rellenan con 0). 2026-11-08
SELECT 'live.evento_actual (reales)' AS tabla, count(*) AS filas,
       count(*) FILTER (WHERE magnitud IS NULL) AS magnitud_nula, count(*) FILTER (WHERE profundidad IS NULL) AS profundidad_nula,
       count(*) FILTER (WHERE pais_codigo IS NULL) AS sin_pais,
       round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / count(*), 2) AS pct_sin_pais
FROM live.evento_actual WHERE NOT sintetico
UNION ALL
SELECT 'replay.evento_actual (reales)', count(*), count(*) FILTER (WHERE magnitud IS NULL), count(*) FILTER (WHERE profundidad IS NULL),
       count(*) FILTER (WHERE pais_codigo IS NULL), round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / count(*), 2)
FROM replay.evento_actual WHERE NOT sintetico
UNION ALL
SELECT 'historico.evento_2025', count(*), count(*) FILTER (WHERE magnitud IS NULL), count(*) FILTER (WHERE profundidad IS NULL),
       count(*) FILTER (WHERE pais_codigo IS NULL), round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / count(*), 2)
FROM historico.evento_2025;

\echo
\echo '== Q17a · UNICIDAD: versiones y eventos duplicados en las tablas de destino (esperado: iguales) =='
-- Mide: la clave (event_id, updated) y la unicidad por event_id en el estado actual. 2026-11-08
SELECT (SELECT count(*) FROM live.versiones_evento WHERE NOT sintetico) AS versiones,
       (SELECT count(*) FROM (SELECT DISTINCT event_id, updated FROM live.versiones_evento WHERE NOT sintetico) x) AS versiones_distintas,
       (SELECT count(DISTINCT event_id) FROM live.versiones_evento WHERE NOT sintetico) AS eventos_con_version,
       (SELECT count(*) FROM live.evento_actual WHERE NOT sintetico) AS eventos_en_estado_actual,
       (SELECT count(DISTINCT event_id) FROM live.evento_actual WHERE NOT sintetico) AS eventos_distintos,
       (SELECT count(*) FROM historico.evento_2025) AS historico_filas,
       (SELECT count(DISTINCT event_id) FROM historico.evento_2025) AS historico_ids_distintos;

\echo
\echo '== Q17b · UNICIDAD, antes: repetición del feed (cada respuesta trae toda la ventana de 24 h) =='
-- Mide: features recibidas frente a versiones distintas persistidas; la diferencia son repeticiones omitidas. 2026-11-08
SELECT sum(features) AS features_recibidas, sum(publicados) AS publicadas, sum(omitidos) AS omitidas_ya_publicadas,
       (SELECT count(*) FROM live.versiones_evento WHERE NOT sintetico) AS versiones_persistidas,
       round(sum(features)::numeric / nullif(sum(publicados), 0), 1) AS features_por_version_publicada
FROM ingesta.consultas;

\echo
\echo '== Q18a · revisiones: eventos por número de versiones guardadas (reales) =='
-- Mide: cuántos eventos fueron revisados por USGS y conservan más de una versión. 2026-11-08
SELECT n_versiones, count(*) AS eventos
FROM (SELECT event_id, count(*) AS n_versiones FROM live.versiones_evento WHERE NOT sintetico GROUP BY 1) t
GROUP BY 1 ORDER BY 1;

\echo
\echo '== Q18b · revisiones: ejemplo de un evento con varias versiones (qué cambió) =='
-- Mide: ejemplos reales de revisión (magnitud, tipo de magnitud, coordenadas y estado). 2026-11-08
SELECT v.event_id, v.updated, v.original -> 'event' -> 'properties' ->> 'mag' AS magnitud,
       v.original -> 'event' -> 'properties' ->> 'magType' AS mag_type, v.original -> 'event' -> 'properties' ->> 'status' AS estado,
       v.original -> 'event' -> 'geometry' -> 'coordinates' AS coordenadas
FROM live.versiones_evento v
WHERE NOT v.sintetico AND v.event_id IN (SELECT event_id FROM live.versiones_evento WHERE NOT sintetico
                                           GROUP BY 1 HAVING count(*) > 1 ORDER BY count(*) DESC, event_id LIMIT 2)
ORDER BY v.event_id, v.updated;

\echo
\echo '== Q19a · VALIDEZ, antes: forma del original (geometría, tipos de fecha y tipo de evento) =='
-- Mide: incumplimientos en los mensajes ya persistidos; el contrato v1 rechaza el resto antes (Q20). 2026-11-08
SELECT count(*) AS versiones,
       count(*) FILTER (WHERE original -> 'event' -> 'geometry' ->> 'type' IS DISTINCT FROM 'Point') AS geometria_no_point,
       count(*) FILTER (WHERE jsonb_typeof(original -> 'event' -> 'properties' -> 'time') IS DISTINCT FROM 'number') AS time_no_numerico,
       count(*) FILTER (WHERE jsonb_typeof(original -> 'event' -> 'properties' -> 'updated') IS DISTINCT FROM 'number') AS updated_no_numerico,
       count(*) FILTER (WHERE original -> 'event' -> 'properties' ->> 'type' IS DISTINCT FROM 'earthquake') AS tipo_no_terremoto
FROM live.versiones_evento WHERE NOT sintetico;

\echo
\echo '== Q19b · VALIDEZ, después: coordenadas, fechas y rangos en el estado actual =='
-- Mide: incumplimientos (esperado 0) y anomalías que NO se rechazan: magnitud y profundidad negativas. 2026-11-08
SELECT 'live.evento_actual (reales)' AS tabla, count(*) AS filas,
       count(*) FILTER (WHERE longitud NOT BETWEEN -180 AND 180 OR latitud NOT BETWEEN -90 AND 90) AS coordenadas_fuera_de_rango,
       count(*) FILTER (WHERE longitud IN ('NaN', 'Infinity', '-Infinity') OR latitud IN ('NaN', 'Infinity', '-Infinity')) AS coordenadas_no_finitas,
       count(*) FILTER (WHERE ocurrencia > now()) AS ocurrencia_futura,
       count(*) FILTER (WHERE updated < ocurrencia) AS updated_anterior_a_ocurrencia,
       count(*) FILTER (WHERE magnitud < 0) AS magnitud_negativa,
       count(*) FILTER (WHERE profundidad < 0) AS profundidad_negativa
FROM live.evento_actual WHERE NOT sintetico
UNION ALL
SELECT 'historico.evento_2025', count(*),
       count(*) FILTER (WHERE longitud NOT BETWEEN -180 AND 180 OR latitud NOT BETWEEN -90 AND 90),
       count(*) FILTER (WHERE longitud IN ('NaN', 'Infinity', '-Infinity') OR latitud IN ('NaN', 'Infinity', '-Infinity')),
       count(*) FILTER (WHERE ocurrencia > now()), count(*) FILTER (WHERE updated < ocurrencia),
       count(*) FILTER (WHERE magnitud < 0), count(*) FILTER (WHERE profundidad < 0)
FROM historico.evento_2025;

\echo
\echo '== Q19c · VALIDEZ: ejemplos de valores negativos que se conservan (no son error) =='
-- Mide: registros reales con profundidad o magnitud negativas y su descripción original. 2026-11-08
(SELECT 'profundidad negativa' AS caso, e.event_id, e.magnitud, e.profundidad, v.original -> 'event' -> 'properties' ->> 'place' AS place
 FROM live.evento_actual e JOIN live.versiones_evento v ON v.event_id = e.event_id AND v.updated = e.updated
 WHERE NOT e.sintetico AND e.profundidad < 0 ORDER BY e.profundidad LIMIT 2)
UNION ALL
(SELECT 'magnitud negativa', e.event_id, e.magnitud, e.profundidad, v.original -> 'event' -> 'properties' ->> 'place'
 FROM live.evento_actual e JOIN live.versiones_evento v ON v.event_id = e.event_id AND v.updated = e.updated
 WHERE NOT e.sintetico AND e.magnitud < 0 ORDER BY e.magnitud LIMIT 2);

\echo
\echo '== Q20 · VALIDEZ, antes: ingesta.cuarentena por motivo y por origen =='
-- Mide: registros rechazados con su motivo. «Real» = ni prefijo synthetic- ni las claves de las pruebas de 001. 2026-11-08
SELECT CASE WHEN substring(clave FROM 1 FOR 10) = 'synthetic-'::bytea THEN 'caso sintético 007 (prefijo synthetic-)'
            WHEN clave IN ('k1'::bytea, 'otra'::bytea, 'us2'::bytea, 'us3'::bytea) THEN 'prueba dañada de 001 (claves k1, otra, us2, us3; sin prefijo)'
            ELSE 'real (feed USGS)' END AS origen,
       motivo, count(*) AS registros, min(recibido_en)::date AS desde, max(recibido_en)::date AS hasta
FROM ingesta.cuarentena GROUP BY 1, 2 ORDER BY 1, 2;

\echo
\echo '== Q21 · CONSISTENCIA: claves geográficas y nombres frente al catálogo (esperado 0) =='
-- Mide: pais_codigo/pais_nombre coherentes entre sí y con ingesta.pais (FK ADM0_A3). 2026-11-08
SELECT 'live.evento_actual (reales)' AS tabla, count(*) AS filas,
       count(*) FILTER (WHERE (e.pais_codigo IS NULL) <> (e.pais_nombre = 'Sin país asignado')) AS codigo_y_nombre_incoherentes,
       count(*) FILTER (WHERE e.pais_codigo IS NOT NULL AND p.codigo IS NULL) AS codigo_sin_catalogo,
       count(*) FILTER (WHERE e.pais_codigo IS NOT NULL AND e.pais_nombre <> p.nombre) AS nombre_distinto_del_catalogo
FROM live.evento_actual e LEFT JOIN ingesta.pais p ON p.codigo = e.pais_codigo WHERE NOT e.sintetico
UNION ALL
SELECT 'historico.evento_2025', count(*),
       count(*) FILTER (WHERE (e.pais_codigo IS NULL) <> (e.pais_nombre = 'Sin país asignado')),
       count(*) FILTER (WHERE e.pais_codigo IS NOT NULL AND p.codigo IS NULL),
       count(*) FILTER (WHERE e.pais_codigo IS NOT NULL AND e.pais_nombre <> p.nombre)
FROM historico.evento_2025 e LEFT JOIN ingesta.pais p ON p.codigo = e.pais_codigo;

\echo
\echo '== Q22 · CONSISTENCIA: el estado actual es la última versión de cada evento (esperado 0) =='
-- Mide: secuencia de revisiones; el estado actual nunca queda por detrás ni por delante del historial. 2026-11-08
SELECT count(*) AS eventos,
       count(*) FILTER (WHERE e.updated <> m.ultima) AS actual_no_es_la_ultima_version,
       count(*) FILTER (WHERE e.updated < e.ocurrencia) AS updated_anterior_a_ocurrencia,
       count(*) FILTER (WHERE m.versiones > 1) AS eventos_con_revisiones
FROM live.evento_actual e
JOIN (SELECT event_id, max(updated) AS ultima, count(*) AS versiones FROM live.versiones_evento GROUP BY 1) m USING (event_id)
WHERE NOT e.sintetico;

\echo
\echo '== Q23 · ACTUALIDAD: retrasos de la primera versión de cada evento real (segundos) =='
-- Mide: tiempos separados: updated-ocurrencia (USGS), ingested_at-updated (nuestra vigilancia del feed) y
-- processed_at-ingested_at (productor→Kafka→consumidor→PostgreSQL). Una «sesión» es un tramo de consultas sin huecos de más de
-- 10 minutos. El primer ciclo de cada sesión recoge todo el feed de las 24 h previas (los retrasos de ese grupo son de arranque,
-- no de operación); los ciclos posteriores son la operación normal. 2026-11-08
WITH c AS (SELECT id, acabada_en,
                  (lag(acabada_en) OVER (ORDER BY id) IS NULL
                   OR acabada_en - lag(acabada_en) OVER (ORDER BY id) > interval '10 minutes')::int AS nueva
           FROM ingesta.consultas),
     s AS (SELECT sesion, min(acabada_en) AS desde, max(acabada_en) AS hasta
           FROM (SELECT acabada_en, sum(nueva) OVER (ORDER BY id) AS sesion FROM c) x GROUP BY sesion),
     p AS (SELECT DISTINCT ON (v.event_id) v.event_id, e.ocurrencia, v.updated, v.ingested_at, v.processed_at
           FROM live.versiones_evento v JOIN live.evento_actual e USING (event_id)
           WHERE NOT v.sintetico ORDER BY v.event_id, v.updated)
SELECT g.grupo, count(*) AS eventos,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM p.updated - p.ocurrencia))::numeric, 0) AS usgs_updated_menos_ocurrencia_mediana_s,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM p.updated - p.ocurrencia))::numeric, 0) AS usgs_updated_menos_ocurrencia_p95_s,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM p.ingested_at - p.updated))::numeric, 1) AS ingesta_menos_updated_mediana_s,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM p.ingested_at - p.updated))::numeric, 1) AS ingesta_menos_updated_p95_s,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM p.processed_at - p.ingested_at))::numeric, 3) AS pipeline_mediana_s,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM p.processed_at - p.ingested_at))::numeric, 3) AS pipeline_p95_s,
       round(max(extract(epoch FROM p.processed_at - p.ingested_at))::numeric, 3) AS pipeline_maximo_s
FROM p JOIN s ON p.ingested_at BETWEEN s.desde - interval '2 minutes' AND s.hasta
CROSS JOIN LATERAL (VALUES ('todas', true),
                           ('primer ciclo de cada sesión (arrastra el feed de 24 h)', p.ingested_at <= s.desde),
                           ('ciclos posteriores (sistema en marcha)', p.ingested_at > s.desde)) AS g(grupo, incluir)
WHERE g.incluir GROUP BY g.grupo ORDER BY g.grupo;

\echo
\echo '== Q24 · ACTUALIDAD: antigüedad de la última consulta correcta y del último evento persistido =='
-- Mide: cuánto lleva el sistema sin datos nuevos en el instante de la ejecución. 2026-11-08
SELECT now() AT TIME ZONE 'UTC' AS ahora_utc,
       (SELECT max(acabada_en) FROM ingesta.consultas WHERE http_status = 200 AND error IS NULL) AS ultima_consulta_ok,
       now() - (SELECT max(acabada_en) FROM ingesta.consultas WHERE http_status = 200 AND error IS NULL) AS edad_ultima_consulta,
       (SELECT max(ocurrencia) FROM live.evento_actual WHERE NOT sintetico) AS ultimo_evento_real,
       (SELECT max(processed_at) FROM live.versiones_evento WHERE NOT sintetico) AS ultima_persistencia_real;

\echo
\echo '== Q25a · EXACTITUD: terremotos sin país asignado, en directo frente a histórico =='
-- Mide: el reparto «Sin país asignado» en cada fuente (el catálogo solo tiene polígonos terrestres). 2026-11-08
SELECT 'live.evento_actual (reales)' AS fuente, count(*) AS eventos, count(*) FILTER (WHERE pais_codigo IS NULL) AS sin_pais,
       round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / count(*), 2) AS pct_sin_pais
FROM live.evento_actual WHERE NOT sintetico
UNION ALL
SELECT 'historico.evento_2025', count(*), count(*) FILTER (WHERE pais_codigo IS NULL),
       round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / count(*), 2)
FROM historico.evento_2025;

\echo
\echo '== Q25b · EXACTITUD: sin país por intervalo de magnitud en el histórico =='
-- Mide: si los sin país se concentran donde cabe esperar (mar abierto) o son un fallo del polígono. 2026-11-08
SELECT CASE WHEN magnitud IS NULL THEN 'ND' WHEN magnitud < 5 THEN '[4, 5)' WHEN magnitud < 6 THEN '[5, 6)' ELSE '>= 6' END AS magnitud,
       count(*) AS eventos, count(*) FILTER (WHERE pais_codigo IS NULL) AS sin_pais,
       round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / count(*), 1) AS pct_sin_pais
FROM historico.evento_2025 GROUP BY 1 ORDER BY 1;

\echo
\echo '== Q25b2 · EXACTITUD: muestras equivalentes (magnitud >= 4): sin país en directo frente a histórico =='
-- Mide: el mismo corte de magnitud en las dos fuentes; en directo hay pocos eventos, la cifra es orientativa. 2026-11-08
SELECT 'live.evento_actual (reales), magnitud >= 4' AS fuente, count(*) AS eventos,
       count(*) FILTER (WHERE pais_codigo IS NULL) AS sin_pais,
       round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / nullif(count(*), 0), 2) AS pct_sin_pais
FROM live.evento_actual WHERE NOT sintetico AND magnitud >= 4
UNION ALL
SELECT 'historico.evento_2025, magnitud >= 4', count(*), count(*) FILTER (WHERE pais_codigo IS NULL),
       round(100.0 * count(*) FILTER (WHERE pais_codigo IS NULL) / nullif(count(*), 0), 2)
FROM historico.evento_2025 WHERE magnitud >= 4;

\echo
\echo '== Q25c · EXACTITUD: ejemplos reales sin país y la descripción original (`place`) =='
-- Mide: qué son los sin país en directo; `place` solo se usa aquí para contrastar, nunca para asignar país. 2026-11-08
SELECT e.event_id, round(e.magnitud::numeric, 1) AS magnitud, e.longitud, e.latitud, v.original -> 'event' -> 'properties' ->> 'place' AS place
FROM live.evento_actual e JOIN live.versiones_evento v ON v.event_id = e.event_id AND v.updated = e.updated
WHERE NOT e.sintetico AND e.pais_codigo IS NULL ORDER BY e.ocurrencia DESC LIMIT 5;

\echo
\echo '== Q25d · EXACTITUD: tipos de magnitud (magType) en los eventos reales en directo =='
-- Mide: por qué la magnitud no es comparable sin más entre tipos (ml, md, mb, mww…). 2026-11-08
SELECT coalesce(v.original -> 'event' -> 'properties' ->> 'magType', '(sin tipo)') AS mag_type, count(*) AS eventos,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM live.evento_actual e JOIN live.versiones_evento v ON v.event_id = e.event_id AND v.updated = e.updated
WHERE NOT e.sintetico GROUP BY 1 ORDER BY 2 DESC;

-- ============================================================================================
-- D. TRANSFORMACIONES (qué cambia los datos y a cuántos registros afecta)
-- ============================================================================================

\echo
\echo '== Q26 · transformaciones y registros afectados (datos reales) =='
-- Mide: el recuento de cada transformación del pipeline (Enunciado §6). 2026-11-08
SELECT 1 AS n, 'ms epoch → timestamptz UTC (ocurrencia y updated)' AS transformacion, 'consumidor' AS donde,
       (SELECT count(*) FROM live.versiones_evento WHERE NOT sintetico) AS registros
UNION ALL SELECT 2, 'país asignado por punto en polígono (ADM0_A3)', 'consumidor', (SELECT count(*) FROM live.evento_actual WHERE NOT sintetico AND pais_codigo IS NOT NULL)
UNION ALL SELECT 3, '«Sin país asignado» conservado (ni error ni país más cercano)', 'consumidor', (SELECT count(*) FROM live.evento_actual WHERE NOT sintetico AND pais_codigo IS NULL)
UNION ALL SELECT 4, 'magnitud nula conservada como NULL (no se rellena con 0)', 'consumidor', (SELECT count(*) FROM live.evento_actual WHERE NOT sintetico AND magnitud IS NULL)
UNION ALL SELECT 5, 'profundidad nula conservada como NULL', 'consumidor', (SELECT count(*) FROM live.evento_actual WHERE NOT sintetico AND profundidad IS NULL)
UNION ALL SELECT 6, 'excluido por type distinto de earthquake (motivo en ingesta.exclusiones)', 'productor', (SELECT coalesce(sum(excluidos), 0) FROM ingesta.consultas)
UNION ALL SELECT 7, 'versión ya publicada omitida (misma (id, updated))', 'productor', (SELECT coalesce(sum(omitidos), 0) FROM ingesta.consultas)
UNION ALL SELECT 8, 'versión anterior conservada en el historial sin ser el estado actual', 'consumidor',
       (SELECT count(*) FROM live.versiones_evento v JOIN live.evento_actual e USING (event_id) WHERE NOT v.sintetico AND v.updated < e.updated)
UNION ALL SELECT 9, 'registro a cuarentena con motivo (solo feed real)', 'consumidor',
       (SELECT count(*) FROM ingesta.cuarentena WHERE substring(clave FROM 1 FOR 10) <> 'synthetic-'::bytea AND clave NOT IN ('k1'::bytea, 'otra'::bytea, 'us2'::bytea, 'us3'::bytea))
UNION ALL SELECT 10, 'histórico: filas cargadas (rechazadas = 18.302 − filas)', 'historico_cargar', (SELECT count(*) FROM historico.evento_2025)
ORDER BY n;

-- ============================================================================================
-- E. PLANES DE EJECUCIÓN de los índices existentes (EXPLAIN real, solo lectura)
-- ============================================================================================

\echo
\echo '== Q27 · lista paginada del estado actual en directo (usa evento_actual_ocurrencia_idx si compensa) =='
-- Mide: el plan real de la consulta de la API con el tamaño actual de live.evento_actual. 2026-11-08
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud, pais_codigo, pais_nombre
FROM live.evento_actual WHERE NOT sintetico ORDER BY ocurrencia DESC, event_id ASC LIMIT 100;

\echo
\echo '== Q28 · la misma consulta sin poder usar el índice (enable_indexscan y enable_bitmapscan = off, solo esta sesión) =='
-- Mide: el plan sin el índice (recorrer la tabla y ordenar) con el mismo tamaño real; sin DDL ni bloqueos. 2026-11-08
SET enable_indexscan = off;
SET enable_bitmapscan = off;
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_id, ocurrencia, updated, magnitud, profundidad, longitud, latitud, pais_codigo, pais_nombre
FROM live.evento_actual WHERE NOT sintetico ORDER BY ocurrencia DESC, event_id ASC LIMIT 100;
RESET enable_indexscan;
RESET enable_bitmapscan;

\echo
\echo '== Q29 · búsqueda por clave primaria (event_id) en el estado actual y en el histórico =='
-- Mide: planes de la clave primaria en las dos tablas, con un id concreto elegido antes. 2026-11-08
SELECT event_id AS id_live FROM live.evento_actual WHERE NOT sintetico ORDER BY ocurrencia LIMIT 1 \gset
SELECT event_id AS id_hist FROM historico.evento_2025 ORDER BY ocurrencia LIMIT 1 \gset
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM live.evento_actual WHERE event_id = :'id_live';
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM historico.evento_2025 WHERE event_id = :'id_hist';

\echo
\echo '== Q30 · recuento por país y ventana en directo (índice (pais_nombre, ocurrencia)) y comparación histórica =='
-- Mide: planes de las dos consultas de agregación principales de la API (recuentos por país y denominador histórico). 2026-11-08
EXPLAIN (ANALYZE, BUFFERS)
SELECT pais_codigo, pais_nombre, count(*) FROM live.evento_actual WHERE NOT sintetico GROUP BY pais_codigo, pais_nombre ORDER BY count(*) DESC, pais_nombre ASC;
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM historico.evento_2025 WHERE magnitud >= 4 AND pais_nombre = 'Chile';

\echo
\echo '== Q30b · plan de «último evento procesado» de /status y de la lista filtrada por país =='
-- Mide: si algún índice sirve a estas dos consultas (la primera es la de api/estado.py; la segunda, la lista con pais_codigo). 2026-11-08
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_id, updated, source, sintetico, processed_at FROM live.evento_actual ORDER BY processed_at DESC LIMIT 1;
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_id, ocurrencia, magnitud FROM live.evento_actual
WHERE NOT sintetico AND pais_codigo = 'USA' ORDER BY ocurrencia DESC, event_id ASC LIMIT 100;

\echo
\echo '== Q31 · esquemas de la base: tras las mediciones no debe quedar `medicion` =='
-- Mide: que el esquema temporal de docs/memoria/mediciones.md se borró (comprobación de T13). 2026-11-08
\dn

\echo
\echo '== fin =='

