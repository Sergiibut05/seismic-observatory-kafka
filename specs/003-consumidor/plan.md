# Plan 003 (compacto)

El contrato v1 no cambia. Lo nuevo es qué se hace con un mensaje ya válido.

- `consumer/calidad.py`: función pura. Exige `Point` con longitud y latitud finitas
  en rango y `properties.time` entero. `mag` y la tercera coordenada (profundidad,
  km) son opcionales; si vienen, tienen que ser un número finito, y puede ser
  negativo. Lo ausente queda en `None`.
- `common/catalogo.py`: además de validar, `construir_indice` guarda los polígonos
  en un `STRtree`. Una geometría inválida se intenta reparar con `buffer(0)`; si
  no queda un polígono, ese país no entra en el índice (el catálogo entregado tiene
  0 inválidas). La asignación es planar en grados, que es el punto-en-polígono
  sobre EPSG:4326 que pide el enunciado.
- `ingesta.pais` (código `ADM0_A3`, nombre, continente, subregión) se carga al
  arrancar. `live.evento_actual` y `replay.evento_actual` son el hecho: una fila
  por `event_id`, con ocurrencia, magnitud, profundidad, coordenadas y país.
  No hay tabla calendario: la hora UTC sale de `date_trunc('hour', ocurrencia)`
  cuando haga falta (feature 005). El grano y la clave están en el `PRIMARY KEY`.
- El `WHERE evento_actual.updated < EXCLUDED.updated` es la regla de «solo la
  revisión más reciente». El historial no se toca.
- `/status` lee `live.evento_actual`. Un volumen que ya tenía versiones se rellena
  una vez al arrancar, en una transacción, sin republicar Kafka.
- La etiqueta de país va al final del log para no cambiar el orden que ya prueban
  los tests del bucle.

## Constitution Check

I sin servicios nuevos. II contrato v1 intacto. III una transacción y el offset
después. IV el estado actual no cuenta mensajes; replay no entra en
`eventos_reales`. V país por polígono y `ADM0_A3`, con «Sin país asignado». VI
nulos sin rellenar; lo inservible va a cuarentena con motivo. VII sin secretos.
VIII el mismo consumidor.
