-- Elimina solo las versiones sintéticas (sintetico = true) de la tabla live.
-- No toca Kafka (los mensajes siguen en el topic hasta que vence la retención) ni la cuarentena.
-- Un dato real nunca puede tener sintetico = true: lo impide un CHECK de la tabla.

BEGIN;
DELETE FROM live.versiones_evento WHERE sintetico;
COMMIT;
