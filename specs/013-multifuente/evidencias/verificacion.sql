-- Verificación de la feature 013 sobre la base real (ejecutar con psql -f).
\pset pager off
\echo '== 1. Nada perdido: informes publicados frente a informes en la fusión (por fuente)'
SELECT p.fuente, p.publicados, i.en_fusion, p.publicados - i.en_fusion AS diferencia
FROM (SELECT fuente, count(DISTINCT event_id) AS publicados FROM ingesta.publicadas GROUP BY fuente) p
JOIN (SELECT fuente, count(*) AS en_fusion FROM fusion.informe GROUP BY fuente) i USING (fuente)
ORDER BY fuente;

\echo '== 2. Todo lo emitido está en la base: eventos fusionados frente al estado actual (misma versión)'
SELECT count(*) AS canonicos,
       count(e.event_id) AS en_estado_actual,
       count(*) FILTER (WHERE e.event_id IS NULL) AS faltan,
       count(*) FILTER (WHERE e.updated <> to_timestamp(c.updated_ms / 1000.0)) AS version_distinta
FROM fusion.canonico c LEFT JOIN live.evento_actual e ON e.event_id = c.id;

\echo '== 3. SC-003: ningún id repetido en el estado actual'
SELECT count(*) AS filas, count(DISTINCT event_id) AS ids_distintos FROM live.evento_actual;

\echo '== 4. Eventos por combinación de fuentes'
SELECT fuentes, count(*) FROM live.evento_actual WHERE NOT sintetico GROUP BY fuentes ORDER BY 2 DESC;

\echo '== 5. SC-002: pares USGS-EMSC dentro de la regla (<= 30 s y <= 100 km), por magnitud USGS'
WITH p AS (
  SELECT a.canonico AS ca, b.canonico AS cb, a.magnitud AS m,
         2 * 6371 * asin(sqrt(power(sin(radians(b.latitud - a.latitud) / 2), 2)
           + cos(radians(a.latitud)) * cos(radians(b.latitud)) * power(sin(radians(b.longitud - a.longitud) / 2), 2))) AS km
  FROM fusion.informe a JOIN fusion.informe b
    ON a.fuente = 'usgs' AND b.fuente = 'emsc' AND b.tiempo_ms BETWEEN a.tiempo_ms - 30000 AND a.tiempo_ms + 30000
)
SELECT CASE WHEN m >= 4 THEN 'M >= 4' ELSE 'M < 4' END AS magnitud,
       count(*) AS pares_en_regla,
       count(*) FILTER (WHERE ca = cb) AS en_el_mismo_evento,
       round(100.0 * count(*) FILTER (WHERE ca = cb) / count(*), 1) AS porcentaje
FROM p WHERE km <= 100 GROUP BY 1 ORDER BY 1;

\echo '== 6. Los pares sin fusionar: ¿el evento ya tenía informe de esa fuente? (caso «dos candidatos»)'
WITH p AS (
  SELECT a.canonico AS ca, b.canonico AS cb,
         2 * 6371 * asin(sqrt(power(sin(radians(b.latitud - a.latitud) / 2), 2)
           + cos(radians(a.latitud)) * cos(radians(b.latitud)) * power(sin(radians(b.longitud - a.longitud) / 2), 2))) AS km
  FROM fusion.informe a JOIN fusion.informe b
    ON a.fuente = 'usgs' AND b.fuente = 'emsc' AND b.tiempo_ms BETWEEN a.tiempo_ms - 30000 AND a.tiempo_ms + 30000
)
SELECT count(*) AS sin_fusionar,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM fusion.informe x WHERE x.canonico = p.ca AND x.fuente = 'emsc')
                           OR EXISTS (SELECT 1 FROM fusion.informe x WHERE x.canonico = p.cb AND x.fuente = 'usgs')) AS porque_ya_tenia_pareja
FROM p WHERE km <= 100 AND ca <> cb;

\echo '== 7. SC-001: Europa (lat 34-72, lon -25..45) en las últimas 24 h, por fuentes'
SELECT fuentes, count(*) FROM live.evento_actual
WHERE NOT sintetico AND ocurrencia > now() - interval '24 hours'
  AND latitud BETWEEN 34 AND 72 AND longitud BETWEEN -25 AND 45
GROUP BY fuentes ORDER BY 2 DESC;

\echo '== 8. Eventos por mes (2025-2026), M >= 2,5'
SELECT to_char(date_trunc('month', ocurrencia), 'YYYY-MM') AS mes, count(*) AS eventos,
       count(*) FILTER (WHERE cardinality(fuentes) = 2) AS fusionados
FROM live.evento_actual
WHERE NOT sintetico AND ocurrencia >= '2025-01-01' AND magnitud >= 2.5
GROUP BY 1 ORDER BY 1;

\echo '== 9. Descartes de la fusión y cuarentena del consumidor'
SELECT 'fusion.descartes' AS tabla, motivo, count(*) FROM fusion.descartes GROUP BY motivo
UNION ALL
SELECT 'ingesta.cuarentena (desde hoy)', motivo, count(*) FROM ingesta.cuarentena
WHERE recibido_en >= date_trunc('day', now()) GROUP BY motivo;
