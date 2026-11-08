# T24 — limpieza y cierre (orquestador)
## Antes
 reales | sint_actual | sint_versiones | sint_cuarentena | replay | historico 
--------+-------------+----------------+-----------------+--------+-----------
    481 |           5 |             14 |               4 |     40 |     18302
(1 row)

## Limpieza

=== Antes: filas sintéticas y reales ===
          tabla          | sinteticas | reales 
-------------------------+------------+--------
 live.evento_actual      |          5 |    481
 live.versiones_evento   |         14 |    553
 replay.evento_actual    |          0 |     40
 replay.versiones_evento |          0 |     41
 ingesta.cuarentena      |          4 |      7

BEGIN

=== Borradas (una fila por tabla) ===
       tabla        | borradas 
--------------------+----------
 live.evento_actual |        5

         tabla         | borradas 
-----------------------+----------
 live.versiones_evento |       14

        tabla         | borradas 
----------------------+----------
 replay.evento_actual |        0

          tabla          | borradas 
-------------------------+----------
 replay.versiones_evento |        0

       tabla        | borradas 
--------------------+----------
 ingesta.cuarentena |        4

COMMIT

=== Después: todo sintético debe ser 0 y los reales quedan igual ===
          tabla          | sinteticas | reales 
-------------------------+------------+--------
 live.evento_actual      |          0 |    481
 live.versiones_evento   |          0 |    553
 replay.evento_actual    |          0 |     40
 replay.versiones_evento |          0 |     41
 ingesta.cuarentena      |          0 |      7

## Después
 reales | sint_actual | sint_versiones | sint_cuarentena | replay | historico 
--------+-------------+----------------+-----------------+--------+-----------
    481 |           0 |              0 |               0 |     40 |     18302
(1 row)

## Segunda ejecución (debe borrar 0)

=== Antes: filas sintéticas y reales ===
          tabla          | sinteticas | reales 
-------------------------+------------+--------
 live.evento_actual      |          0 |    481
 live.versiones_evento   |          0 |    553
 replay.evento_actual    |          0 |     40
 replay.versiones_evento |          0 |     41
 ingesta.cuarentena      |          0 |      7

BEGIN

=== Borradas (una fila por tabla) ===
       tabla        | borradas 
--------------------+----------
 live.evento_actual |        0

         tabla         | borradas 
-----------------------+----------
 live.versiones_evento |        0

        tabla         | borradas 
----------------------+----------
 replay.evento_actual |        0

          tabla          | borradas 
-------------------------+----------
 replay.versiones_evento |        0

       tabla        | borradas 
--------------------+----------
 ingesta.cuarentena |        0

COMMIT

=== Después: todo sintético debe ser 0 y los reales quedan igual ===
          tabla          | sinteticas | reales 
-------------------------+------------+--------
 live.evento_actual      |          0 |    481
 live.versiones_evento   |          0 |    553
 replay.evento_actual    |          0 |     40
 replay.versiones_evento |          0 |     41
 ingesta.cuarentena      |          0 |      7

## /status
{"base_de_datos":"conectada","eventos_reales":481,"eventos_sinteticos":0,"eventos_replay":40,"ultimo_evento":{"event_id":"us7000twxf","updated":"2026-11-08T14:54:07.131Z","source":"usgs","sintetico":false,"processed_at":"2026-11-08T14:55:37.708Z"},"ultima_ingesta_correcta":"2026-11-08T14:55:37.701Z","periodo_consultado":{"desde":"2026-11-01T15:04:56.675Z","hasta":"2026-11-08T14:46:03.596Z"},"datos_desactualizados":false,"umbral_datos_desactualizados_segundos":300,"generated_at":"2026-11-08T14:56:02.110Z"}

## Secretos y ficheros locales
- `git ls-files` no contiene `.env`; `git status` no muestra `.env`, `data/` ni `dist/`.
- `git grep` de authtoken, URL de ngrok y contraseñas: solo la URL ficticia `https://abc-123.ngrok-free.app` de `config.service.spec.ts` y el script del README que pide la contraseña sin guardarla.
- Panel: Vitest 270 tests pasados; `npm run build` sin errores (único aviso, ya existente: Leaflet no es ESM).
- Backend: pytest 780 tests pasados en la imagen (bloque A; el código del backend no cambió después).

T24 la hizo el orquestador, no el verifier.
