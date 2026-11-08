# T18 — Pruebas de aceptación `docs/ENUNCIADO.md` §11 (en vivo)

**Fecha:** 2026-11-08 (UTC)  
**Rama:** `007-memoria`  
**API:** `http://127.0.0.1:8000` (contrato 0.3.0)  
**Stack:** `docker compose ps` — todos healthy al cierre.

## Recuentos de eventos reales (sin sintéticos)

| Momento | `live.evento_actual` (reales) | `live.evento_actual` (total) | `live.versiones_evento` | `replay.evento_actual` | `ingesta.cuarentena` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Inicio T18 | 480 | 485 | 537 | 40 | 8 |
| Fin T18 | 480 | 485 | 544 | 40 | 11 |

Los reales no cambian. Suben `versiones_evento` y `cuarentena` al republicar el lote de casos (mensajes nuevos en Kafka, incluida cuarentena sin deduplicación por `event_id`).

---

## Tabla resumen

| # | Prueba (§11 / AC) | Resultado | Evidencia |
| --- | --- | --- | --- |
| 1 | Evento real en API (AC-8) | **superada** | `t18-evento-real-logs.txt`, `t18-status-final.json` |
| 2 | Versión posterior (`synthetic-caso-revision`) | **superada** | `t18-sql-sinteticos.txt` |
| 3 | Versión antigua no sustituye | **superada** | `t18-sql-sinteticos.txt` |
| 4 | Duplicado / reenvío → `omitido` | **superada** | `t18-casos-reenvio.txt`, logs consumidor |
| 5 | Magnitud nula → NULL / `null` API | **superada** | `t18-eventos-replay.json` (muestra live), consulta API inline en §5 |
| 6 | Coordenadas inválidas → cuarentena | **superada** | `t18-sql-sinteticos.txt` |
| 7 | Evento marítimo → «Sin país asignado» | **superada** | `t18-recuentos-pais-sinteticos.json` |
| 8 | Reinicio consumidor, lag 0 | **superada** | `t18-consumer-lag.txt`, `t18-casos-restart.txt` |
| 9 | Cerrar túnel (`stop api`) | **superada** | `t18-api-cerrado.txt` |
| 10 | Abrir túnel (`start api`) | **superada** | `t18-health-abierto.json`, `t18-status-abierto.json` |
| 11 | Reproducción histórica (AC-14) | **superada** | `t18-replay-run.txt`, `t18-eventos-replay.json`, `t18-recuentos-pais-replay.json` |
| — | `/comparacion-historica?modo=replay` → 400 (AC-19) | **superada** | respuesta en §11 anexo |

**Limpieza (AC-15):** no ejecutada en T18 (sintéticos deben permanecer para capturas T19).

---

## Detalle por prueba

### 1. Evento nuevo (real)

**Comando:**

```powershell
curl.exe -s http://127.0.0.1:8000/status
docker compose logs producer --tail 200 | Select-String "nc75463972"
docker compose logs consumer --tail 300 | Select-String "nc75463972"
```

**Salida recortada (`/status` al inicio de T18):**

```json
"ultimo_evento":{"event_id":"nc75463972","source":"usgs","sintetico":false,"processed_at":"2026-11-08T14:28:33.183Z"},
"ultima_ingesta_correcta":"2026-11-08T14:30:33.478Z"
```

Diferencia ≈ 2 min entre `processed_at` del último evento real y `ultima_ingesta_correcta`.

**Logs (`t18-evento-real-logs.txt`):**

```
service=producer result=publicado event_id=nc75463972 updated=1794148042058 source=usgs
service=consumer result=persistido event_id=nc75463972 updated=1794148042058 ... pais="Estados Unidos"
```

**Resultado:** **superada** — mismo `event_id` en productor y consumidor; la API refleja ingesta reciente del flujo USGS.

---

### 2. Versión posterior

**SQL** (`t18-sql-sinteticos.txt`):

```
revision_mag=4.5 | revision_pais=Francia | revision_versiones=6
```

Estado actual: magnitud 4.5 y país Francia (v2 del caso `revision`). El historial tiene varias filas en `live.versiones_evento` para `synthetic-caso-revision` (6 tras republicaciones del lote).

**Resultado:** **superada**

---

### 3. Versión antigua

Tras publicar el paso `antigua` (`updated` B−60 s, M 9.0), el estado actual sigue en Francia / 4.5 con `updated=2026-11-08 13:01:00+00` (v2), no en la magnitud 9.0.

**Resultado:** **superada**

---

### 4. Duplicado / reenvío

**Comando:**

```powershell
docker compose exec -T producer python -m observatorio.producer.casos
```

**Salida:** `t18-casos-reenvio.txt` — caso `reenvio` republica el mismo mensaje.

**Antes/después:** `live.evento_actual` 485 → 485; reales 480 → 480.

**Consumidor:**

```
result=omitido event_id=synthetic-caso-nuevo updated=1794146400000 reason=duplicado
```

**Nota:** `live.versiones_evento` pasó de 537 a 544 en la primera republicación del lote (nuevos offsets en Kafka); el recuento de **estado actual** y de **reales** no cambia.

**Resultado:** **superada**

---

### 5. Magnitud nula

**API:**

```powershell
curl.exe -s "http://127.0.0.1:8000/eventos?incluir_sinteticos=true"
```

Evento `synthetic-caso-magnitud-nula`: `"magnitud": null`. SQL: magnitud vacía (NULL) en `live.evento_actual`.

**Resultado:** **superada**

---

### 6. Coordenadas inválidas

**SQL:**

```
clave_text=synthetic-caso-coordenadas-invalidas | motivo=coordenadas_fuera_de_rango
```

No aparece en `/eventos?incluir_sinteticos=true` (solo 5 sintéticos en estado actual). Cuarentena crece al republicar (8 → 11 filas; una por offset Kafka).

**Resultado:** **superada**

---

### 7. Evento marítimo

**SQL:** `synthetic-caso-mar` → `pais_nombre = Sin país asignado`, `pais_codigo` NULL.

**API:** `t18-recuentos-pais-sinteticos.json` incluye categoría `"Sin país asignado","recuento":98` (reales + sintéticos con interruptor equivalente).

**Resultado:** **superada**

---

### 8. Reinicio del consumidor

**Comandos:**

```powershell
docker compose exec -T producer python -m observatorio.producer.casos
docker compose restart consumer
docker compose exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group consumidor-live
```

**Lag:** `t18-consumer-lag.txt` — **LAG=0** en todas las particiones de `eventos.live` y `eventos.replay`.

**Recuentos:** reales 480 antes y después; `live.evento_actual` 485 estable.

**Resultado:** **superada**

---

### 9. Cerrar el túnel

**Comando:** `docker compose stop api`

**Comprobación:** `curl.exe -s -w "HTTP_CODE:%{http_code}" http://127.0.0.1:8000/health` → `t18-api-cerrado.txt` con `HTTP_CODE:000` (sin conexión).

**Resultado:** **superada** (equivalente local a panel sin API).

---

### 10. Abrir el túnel

**Comando:** `docker compose start api`

**Salida:** `t18-health-abierto.json` → `{"status":"ok"}`; `t18-status-abierto.json` con `base_de_datos":"conectada"`.

**Resultado:** **superada** — sin reiniciar el resto de servicios.

---

### 11. Reproducción histórica

**Comando:**

```powershell
docker compose exec -T producer python -m observatorio.replay
```

**SQL antes/después:** `live.evento_actual` 485 / reales 480 sin cambio; `replay.evento_actual` = 40.

**Log productor (`t18-replay-run.txt`):** `etiqueta=REPRODUCCIÓN` en cada publicación; casos `duplicado` y `revision` para `us6000pjr6`.

**Consumidor (segunda ejecución):** `result=omitido ... etiqueta=REPRODUCCIÓN` en duplicado; `us6000pjr6` con `updated=1742247297040` en revisión omitida (ya persistida).

**API:**

| Comprobación | Valor |
| --- | ---: |
| `/eventos?modo=replay` → `total` | 40 |
| Suma `/recuentos/pais?modo=replay` | 40 |
| `count(*)` `replay.evento_actual` | 40 |
| `reproducido_en` presente (ej.) | `2026-11-02T15:22:35.027Z` |
| `ocurrencia` original (ej.) | `2025-01-01T15:08:00.601Z` |

**Revisión replay:** `replay.versiones_evento` tiene 2 filas para `us6000pjr6`; estado actual con `updated` posterior a la primera versión.

**Resultado:** **superada**

### Anexo AC-19

```powershell
curl.exe -s "http://127.0.0.1:8000/comparacion-historica?modo=replay"
```

`{"error":"parametro_invalido","parametro":"modo"}` HTTP 400 — **superada**

---

## Fallos para el developer

Ningún fallo funcional bloqueante detectado en las once pruebas. Observaciones menores:

1. **Republicar `casos` aumenta `live.versiones_evento` y filas de cuarentena** aunque el estado actual y los reales no cambien (comportamiento ya documentado en T5 para cuarentena).
2. Tras varias republicaciones, **`/status`.`ultimo_evento` puede ser sintético** (último `processed_at` del consumidor), no el último USGS; conviene documentar en la memoria si se usa `/status` como demo del flujo real.

---

## Estado final

- API **levantada** (`docker compose ps api` → healthy en `127.0.0.1:8000`).
- Sintéticos **sin borrar** (AC-15 pendiente de limpieza voluntaria).
