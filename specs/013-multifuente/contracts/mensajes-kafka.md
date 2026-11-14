# Contratos Kafka 013

## Topics

| Topic | Escribe | Lee | Contrato | Clave |
|---|---|---|---|---|
| `eventos.usgs` | productor USGS, relleno | fusión | fuente v1 | id USGS |
| `eventos.emsc` | productor EMSC, relleno | fusión | fuente v1 | id EMSC (`unid`) |
| `eventos.live` | fusión (y la prueba de humo y los casos sintéticos, en v1) | consumidor | v2 (o v1) | id canónico (o id del evento v1) |
| `eventos.replay` | reproducción | consumidor | v1 | id USGS |

Todos con 3 particiones y la retención de `TOPIC_RETENTION_MS` (7 días). Los crean los productores; la fusión espera a que existan.

## Fuente v1 (igual que el v1 de 001)

```json
{
  "schema_version": 1,
  "source": "emsc",
  "ingested_at": "2026-11-14T10:00:00.123Z",
  "mode": "live",
  "event": { "...": "el evento tal como lo devuelve la fuente" }
}
```

- `event.id`: id en la fuente. USGS: el `id` del feature. EMSC: el `id` del feature (= `properties.unid`).
- Versión: USGS `event.properties.updated` (ms). EMSC `event.properties.lastupdate` (ISO 8601 UTC).
- Hora de ocurrencia: USGS `event.properties.time` (ms). EMSC `event.properties.time` (ISO 8601 UTC).
- Profundidad: USGS `event.geometry.coordinates[2]`. EMSC `event.properties.depth` (la geometría la trae con el signo cambiado).

## Evento fusionado v2 (`eventos.live`)

```json
{
  "schema_version": 2,
  "source": "emsc",
  "ingested_at": "2026-11-14T10:00:05.000Z",
  "mode": "live",
  "event": {
    "type": "Feature",
    "id": "us7000abcd",
    "geometry": { "type": "Point", "coordinates": [13.07, 42.34, 9.8] },
    "properties": {
      "time": 1794470946480,
      "updated": 1794471012345,
      "mag": 4.3,
      "magType": "mw",
      "place": "CENTRAL ITALY",
      "type": "earthquake"
    }
  },
  "fuentes": [
    { "fuente": "emsc", "id": "20261114_0000123", "updated": 1794471012345, "principal": true,  "original": { "...": "..." } },
    { "fuente": "usgs", "id": "us7000abcd",       "updated": 1794471000000, "principal": false, "original": { "...": "..." } }
  ]
}
```

- **Clave** = `event.id` = id canónico.
- `source` = la fuente principal; `fuentes` ordenada por `fuente`; exactamente una con `principal: true`, y es la de `source`.
- `event` está normalizado con la forma de USGS (la que ya valida el consumidor): `time` y `updated` en ms, profundidad en `coordinates[2]`.
- `event.properties.updated` = versión del evento fusionado: `max(updated de sus fuentes, versión anterior + 1)`.
- `ingested_at` = el máximo de los `ingested_at` de los mensajes de fuente que lo componen.
- Determinista: la misma entrada da el mismo JSON (claves en orden fijo).

### Validación en el consumidor (motivos nuevos, lista cerrada)

| Motivo | Cuándo |
|---|---|
| `fuentes_invalidas` | `fuentes` no es una lista no vacía de objetos con `fuente`, `id`, `updated`, `principal` y `original` |
| `fuentes_repetidas` | dos entradas con la misma `fuente` |
| `principal_incoherente` | no hay exactamente una principal o no coincide con `source` |
| `mode_invalido` | v2 con `mode` distinto de `live` |

Los motivos de v1 (`campo_ausente`, `clave_distinta_de_id`, `updated_invalido`…) siguen igual. En v1 el campo `fuentes` no se admite (`campo_ausente` por campo desconocido).
