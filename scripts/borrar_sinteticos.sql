-- Borra todo dato sintético (feature 007, FR-012, AC-15). Idempotente: una segunda ejecución borra 0 filas.
--
--   Get-Content -Raw scripts/borrar_sinteticos.sql | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f -'
--
-- Una sola transacción, en este orden:
--   1. live.evento_actual                   WHERE sintetico
--   2. live.versiones_evento                WHERE sintetico
--   3. replay.evento_actual                 WHERE sintetico   (por si alguien publicó casos allí)
--   4. replay.versiones_evento              WHERE sintetico
--   5. ingesta.cuarentena                   por prefijo de `clave` (no tiene columna `sintetico`)
--
-- Lo real no se toca: las cuatro primeras condiciones son por `sintetico` y un CHECK de cada tabla impide
-- que un dato real lo tenga a true o un id `synthetic-`. En cuarentena `clave` (bytea) guarda el id del
-- evento, así que se compara el prefijo en bytes; no se usa convert_from porque fallaría con claves
-- que no son UTF-8. No toca Kafka: los mensajes siguen en el topic hasta que vence la retención, pero
-- el grupo del consumidor ya confirmó su offset y no los vuelve a leer.

\set ON_ERROR_STOP on
\pset footer off

\echo
\echo === Antes: filas sintéticas y reales ===
SELECT 'live.evento_actual' AS tabla,
       count(*) FILTER (WHERE sintetico) AS sinteticas, count(*) FILTER (WHERE NOT sintetico) AS reales
  FROM live.evento_actual
UNION ALL
SELECT 'live.versiones_evento', count(*) FILTER (WHERE sintetico), count(*) FILTER (WHERE NOT sintetico)
  FROM live.versiones_evento
UNION ALL
SELECT 'replay.evento_actual', count(*) FILTER (WHERE sintetico), count(*) FILTER (WHERE NOT sintetico)
  FROM replay.evento_actual
UNION ALL
SELECT 'replay.versiones_evento', count(*) FILTER (WHERE sintetico), count(*) FILTER (WHERE NOT sintetico)
  FROM replay.versiones_evento
UNION ALL
SELECT 'ingesta.cuarentena',
       count(*) FILTER (WHERE substring(clave from 1 for 10) = 'synthetic-'::bytea),
       count(*) FILTER (WHERE clave IS NULL OR substring(clave from 1 for 10) <> 'synthetic-'::bytea)
  FROM ingesta.cuarentena;

BEGIN;

\echo
\echo === Borradas (una fila por tabla) ===
WITH borradas AS (DELETE FROM live.evento_actual WHERE sintetico RETURNING 1)
SELECT 'live.evento_actual' AS tabla, count(*) AS borradas FROM borradas;

WITH borradas AS (DELETE FROM live.versiones_evento WHERE sintetico RETURNING 1)
SELECT 'live.versiones_evento' AS tabla, count(*) AS borradas FROM borradas;

WITH borradas AS (DELETE FROM replay.evento_actual WHERE sintetico RETURNING 1)
SELECT 'replay.evento_actual' AS tabla, count(*) AS borradas FROM borradas;

WITH borradas AS (DELETE FROM replay.versiones_evento WHERE sintetico RETURNING 1)
SELECT 'replay.versiones_evento' AS tabla, count(*) AS borradas FROM borradas;

WITH borradas AS (
    DELETE FROM ingesta.cuarentena WHERE substring(clave from 1 for 10) = 'synthetic-'::bytea RETURNING 1
)
SELECT 'ingesta.cuarentena' AS tabla, count(*) AS borradas FROM borradas;

COMMIT;

\echo
\echo === Después: todo sintético debe ser 0 y los reales quedan igual ===
SELECT 'live.evento_actual' AS tabla,
       count(*) FILTER (WHERE sintetico) AS sinteticas, count(*) FILTER (WHERE NOT sintetico) AS reales
  FROM live.evento_actual
UNION ALL
SELECT 'live.versiones_evento', count(*) FILTER (WHERE sintetico), count(*) FILTER (WHERE NOT sintetico)
  FROM live.versiones_evento
UNION ALL
SELECT 'replay.evento_actual', count(*) FILTER (WHERE sintetico), count(*) FILTER (WHERE NOT sintetico)
  FROM replay.evento_actual
UNION ALL
SELECT 'replay.versiones_evento', count(*) FILTER (WHERE sintetico), count(*) FILTER (WHERE NOT sintetico)
  FROM replay.versiones_evento
UNION ALL
SELECT 'ingesta.cuarentena',
       count(*) FILTER (WHERE substring(clave from 1 for 10) = 'synthetic-'::bytea),
       count(*) FILTER (WHERE clave IS NULL OR substring(clave from 1 for 10) <> 'synthetic-'::bytea)
  FROM ingesta.cuarentena;
