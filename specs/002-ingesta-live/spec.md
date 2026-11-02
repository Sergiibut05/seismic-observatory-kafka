# Feature 002: Ingesta live de USGS

**Rama**: `002-ingesta-live` | **Depende de**: 001-esqueleto (contrato v1, topic `eventos.live`, consumidor idempotente)

El productor consulta el feed de las últimas 24 h de USGS cada 60 s, publica solo
lo nuevo o revisado y recuerda qué versiones ya tienen acuse de Kafka. El
consumidor de la 001 no cambia: un reenvío no duplica filas.

## Requisitos

- **FR-001** (Enunciado §4.1, §5): `GET` a `USGS_FEED_URL` (defecto
  `all_day.geojson`) cada `POLL_INTERVAL_SECONDS` (defecto 60). Timeout
  configurable. HTTP 429/5xx, timeout y corte de red se reintentan con la espera
  progresiva ya existente. Un JSON ilegible se registra (`result=error`) y no
  borra el estado anterior.
- **FR-002** (Enunciado §5): antes de transformar, guarda el GeoJSON original en
  `data/usgs` (montado en el productor). Si el SHA-256 coincide con la última
  copia, no escribe otra. Borra copias más viejas que `FEED_RETENTION_HOURS`
  (defecto 48). Cada consulta queda en `ingesta.consultas` (url, fecha, HTTP,
  bytes, sha256, recuentos, error).
- **FR-003** (Enunciado §4.1): solo publica `properties.type == "earthquake"`.
  El resto se anota en `ingesta.exclusiones` con motivo `tipo_no_terremoto`.
  Sin `id` o con `updated` no usable: motivo `sin_id` o `updated_invalido`, y
  no se publica.
- **FR-004** (Enunciado §5, §7): compara `(id, updated)` con
  `ingesta.publicadas`. Publica los nuevos y las revisiones no vistas; omite
  las ya publicadas (`result=omitido`). Clave Kafka = `id`. Mensaje v1 con
  `source=usgs`, `mode=live` e `ingested_at` de esta consulta. El evento va
  tal cual.
- **FR-005** (Enunciado §5; Constitución III): `result=publicado` y la fila en
  `ingesta.publicadas` solo después de `send_and_wait`. Si el proceso cae
  entre el acuse y el insert, el siguiente ciclo republica: el consumidor ya
  lo tolera.
- **FR-006** (Enunciado §5): que un evento desaparezca del feed no lo borra de
  `publicadas` ni de PostgreSQL. Documentado en el README, junto con cómo
  cubrir un hueco de más de 24 h (catálogo FDSN, feature 004).

## Fuera de alcance

Validación de coordenadas, país, cuarentena de contenido y estado «actual»
(003). Descarga del histórico y replay (004). Gráficos (005–006).

## Hecho cuando

Con la pila en marcha, en menos de dos ciclos el log del productor muestra
`result=publicado` o `result=omitido` con `event_id` reales de USGS, `/status`
sube `eventos_reales`, repetir el ciclo no aumenta el recuento, y un fallo
forzado de red deja la última fila de `ingesta.publicadas` intacta.
