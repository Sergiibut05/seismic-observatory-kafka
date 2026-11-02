# Plan 002 (compacto)

Se reutiliza el contrato v1 (`construir_mensaje`), el topic y el consumidor de
la 001. Lo nuevo vive en el productor.

- `backend/observatorio/producer/feed.py`: funciones puras (clasificar eventos,
  decidir si el HTTP es transitorio, conservar el original por SHA-256).
- `backend/observatorio/producer/ciclo.py`: una pasada async (descarga → archivo
  → comparar estado → publicar → marcar). El bucle, en `app.py`, corre al lado
  del supervisor de Kafka y de una conexión a PostgreSQL. USGS caído no tumba
  el contenedor ni marca la salud en rojo: la salud sigue siendo Kafka +
  PostgreSQL.
- `db/init/002_ingesta_live.sql`: `ingesta.publicadas (event_id, updated_ms)`,
  `ingesta.consultas`, `ingesta.exclusiones`. El productor también las crea al
  arrancar (`CREATE TABLE IF NOT EXISTS`) para no depender de un volumen vacío.
- `source` fijo `usgs`. No es sintético: el prefijo reservado sigue siendo
  `synthetic-`.
- Sin dependencia HTTP nueva: `urllib.request` en un hilo.

## Constitution Check

I Compose y backoff ya existentes; se añaden variables al productor. II contrato
v1 sin subir versión. III marca de publicado tras el acuse; el consumidor no se
toca. IV original y consulta se guardan; un fallo no borra estado. V el
catálogo no interviene aún. VI el feed real no usa el prefijo sintético. VII
sin secretos nuevos; el productor pasa a leer `POSTGRES_PASSWORD` para el
estado, ya redactada en los logs. VIII sin servicios nuevos.
