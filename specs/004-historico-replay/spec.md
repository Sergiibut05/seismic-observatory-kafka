# Feature 004: Histórico 2025 y reproducción

**Rama**: `004-historico-replay` | **Depende de**: 001 (esquema `replay`, contrato v1) y 002

Descarga el catálogo USGS de 2025 (magnitud ≥ 4, tipo earthquake, mundo), una vez, y lo
reprocede por Kafka sin mezclarlo con el feed live.

## Requisitos

- **FR-001** (Enunciado §4.2): `python -m observatorio.historico` baja 2025 mes a mes.
  Si USGS rechaza la consulta por superar 20.000 resultados, parte el intervalo y
  reintenta. No se trunca en silencio. Los extremos compartidos se deduplican por
  `(id, updated)`. El manifiesto guarda url, fecha, HTTP y recuentos. Los ficheros
  van a `data/historico/` (fuera de Git).
- **FR-002** (Enunciado §11): `python -m observatorio.replay` publica una selección
  ordenada por `properties.time` en el topic `eventos.replay`, con `mode=replay`,
  el evento original intacto y `ingested_at` como tiempo de reproducción. Pausa
  corta entre mensajes. El log lleva `etiqueta=REPRODUCCIÓN`.
- **FR-003** (Enunciado §11): el mismo consumidor escribe en `replay.versiones_evento`.
  `/status` (`eventos_reales`) no cambia. Incluye un duplicado (no crea fila) y una
  revisión posterior del mismo `id` (sí crea otra versión).
- **FR-004** (Enunciado §5): un hueco live de más de 24 h se recupera con este
  catálogo, no releyendo `all_day`. Queda dicho en el README.

## Hecho cuando

El manifiesto tiene los 12 meses, el replay deja filas solo en `replay.versiones_evento`
y `eventos_reales` no se mueve.
