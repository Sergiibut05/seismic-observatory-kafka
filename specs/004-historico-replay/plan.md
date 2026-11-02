# Plan 004 (compacto)

El feed live y `live.versiones_evento` no se tocan. Lo nuevo es una descarga
fuera de línea y un segundo topic que el mismo consumidor ya sabe enrutar
(`decidir` mapea `mode=replay` al esquema `replay`).

- `backend/observatorio/historico.py`: meses de 2025, consulta FDSN
  (`minmagnitude=4`, `eventtype=earthquake`, `orderby=time-asc`). Un HTTP 400
  que habla de 20.000 resultados, o un 200 con 20.000 features, parte el
  intervalo. 204 es un mes vacío. Extremos compartidos se deduplican por
  `(id, updated)`. Escribe `data/historico/{año}/eventos.geojson` y
  `manifest.json`. `urllib` propio, sin psycopg, para poder correrlo en el
  anfitrión.
- `backend/observatorio/replay.py`: ordena por `properties.time`, publica en
  `eventos.replay` con `construir_mensaje(..., mode=replay)`. El primero se
  republica igual (duplicado) y otra vez con `updated` + 60 s (revisión).
  `ingested_at` es el reloj de la reproducción; `properties.time` no se cambia.
  La etiqueta `REPRODUCCIÓN` va solo en el log: el contrato v1 rechaza campos
  de más en la raíz.
- El productor crea `eventos.live` y `eventos.replay` al arrancar. El
  consumidor espera los dos y se suscribe a ambos con el mismo grupo
  `consumidor-live`, así el topic nuevo empieza en `earliest` y el live no se
  relee. Crea `replay.versiones_evento` al arrancar (`CREATE TABLE IF NOT
  EXISTS`) porque el volumen ya existente no reejecuta `db/init`.
- `ingesta.version_esquema` gana la fila `3 / replay`. La versión mínima que
  exige el código sigue siendo 1.

## Constitution Check

I mismos cinco servicios y backoff. II contrato v1, `schema_version` sigue en
1. III acuse antes de dar por publicado; offset tras el commit. IV el histórico
no pisa el estado live ni `eventos_reales`. V el país sigue siendo de la 003.
VI `source=usgs`, sin prefijo `synthetic-`. VII sin secretos nuevos. VIII sin
servicios nuevos.
