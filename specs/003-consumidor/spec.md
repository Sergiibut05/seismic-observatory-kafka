# Feature 003: Consumidor, país y estado actual

**Rama**: `003-consumidor` | **Depende de**: 001 (historial y cuarentena) y 002 (eventos reales ya guardados)

El consumidor deja de archivar el mensaje tal cual. Comprueba que se puede tratar,
le asigna un país por la geometría y mantiene una fila de estado actual por evento.

## Requisitos

- **FR-001** (Enunciado §6): un evento sin `Point`, con coordenadas no finitas o fuera
  de rango, o sin `properties.time` entero, va a cuarentena con motivo. No entra en
  el historial ni en el estado actual. Magnitud y profundidad ausentes se quedan en
  nulo; no se rellenan con 0. Una magnitud negativa y una profundidad negativa se
  aceptan.
- **FR-002** (Enunciado §4.3): el país sale de contener el punto en un polígono del
  catálogo (EPSG:4326, código `ADM0_A3`). El texto `place` no se consulta. Si varios
  polígonos contienen el punto, gana el de menor área. Sin contención: código nulo y
  nombre «Sin país asignado».
- **FR-003** (Enunciado §7): `evento_actual` tiene una fila por `event_id`. Solo se
  sustituye si el `updated` entrante es estrictamente posterior. El historial
  `(event_id, updated)` sigue insertándose con `ON CONFLICT DO NOTHING` y no se
  sobrescribe. Historial y estado actual van en la misma transacción.
- **FR-004**: lo mismo en el esquema `replay`. `eventos_reales` de `/status` cuenta
  filas de `live.evento_actual`, no mensajes ni versiones.
- **FR-005**: al arrancar, el consumidor carga la dimensión `ingesta.pais` desde el
  catálogo y rellena el estado actual con las versiones que ya estaban en el volumen.
