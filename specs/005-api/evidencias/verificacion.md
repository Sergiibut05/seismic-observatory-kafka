# Verificación feature 005-api (verifier)

**Fecha:** 2026-11-02  
**Rama:** `005-api` (sin cambios de código; solo este fichero y `tasks.md`)  
**API:** `http://127.0.0.1:8000`  
**Datos al inicio:** `live.evento_actual` 257 filas (255→258 reales durante la sesión por ingesta USGS), 2 sintéticos, `replay.evento_actual` 40, `historico.evento_2025` 18.302.

---

## 1. Pytest (imagen consumer)

```powershell
Set-Location "c:\Users\mnsa1\Desktop\Paginas Web y Proyectos\seismic-observatory-kafka"
docker compose run --build --rm --no-deps -e POSTGRES_PASSWORD=x -e PYTHONUNBUFFERED=1 consumer pytest -q --tb=short -p no:cacheprovider
```

**Salida:** `642 passed, 1 warning in 2.95s` (warning: opción pytest `cache_dir` desconocida).

| FR/Tarea | Veredicto |
| --- | --- |
| Suite unitaria 005 + regresión | **PASA** |

---

## 2. Tabla AC / FR (vivo + SQL)

Convención filtros comunes: por defecto solo reales (`NOT sintetico`). Contraste SQL vía:

```powershell
@'
SELECT ...
'@ | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A'
```

| AC / FR | Comando (resumido) | Salida resumida | Veredicto |
| --- | --- | --- | --- |
| **FR-010, AC-7** | `GET /eventos`, `/eventos/mapa`, `/recuentos/*`, `/distribuciones/magnitud` sin filtros; SQL `count(*) … NOT sintetico` | API: total **256** en lista/mapa/país/subregión/hora/dist (256 reales en status); SQL reales **255** al primer muestreo, **256** tras ingesta; suma categorías país = total | **PASA** (coherencia interna API; SQL ±1 por ingesta en curso) |
| **AC-7** (rango fijo) | `desde=2026-11-01T00:00:00Z&hasta=2026-11-03T00:00:00Z` en todos; SQL mismo rango | SQL **255**; lista/mapa/país/sub/hora/dist **255**; suma país **255** | **PASA** |
| **FR-003, AC-4** | `GET /recuentos/pais`; `GET /eventos?pais=Sin%20pa%C3%ADs%20asignado` | Categoría `codigo=null`, recuento **49**; lista filtrada **49** | **PASA** |
| **FR-004, AC-5** | `GET /recuentos/hora?desde=…&hasta=…` (48 h) y ventana 6 h | 48 ventanas, **23** con `recuento=0`; 6 h → **6** ventanas (datos densos: 0 ceros en ese tramo) | **PASA** (ceros en vivo + lógica borde en `test_calculos.py`) |
| **FR-006, AC-6** | `GET /comparacion-historica`; SQL `18302/365`; `?pais=ATA` | `media_diaria=50.1425` (= 18302/365); ventana 24 h mag≥4 **31** (SQL `live_24h_mag4=31`); ATA `media_diaria=0.0`, `cociente=null`, aviso presente | **PASA** |
| **FR-009, AC-8** | Totales sin/`incluir_sinteticos=true`; SQL `replay` count | Default **256** vs sintéticos **258** (+2); `replay.evento_actual` **40** sin cambio; grep `replay` en `api/` **0** | **PASA** |
| **FR-008** | `GET /eventos?magnitud_min=abc` | **400** `{"error":"parametro_invalido","parametro":"magnitud_min"}` | **PASA** |
| **FR-008** (inyección) | `GET /eventos?subregion='; DROP TABLE x;--&limite=1` | **200**, `total=0` (valor parametrizado) | **PASA** |
| **FR-011, AC-9** | `curl -X OPTIONS … Origin: http://localhost:4200` + header ngrok | **200**, `access-control-allow-origin: http://localhost:4200`, métodos GET/OPTIONS | **PASA** |
| **AC-9** | `OPTIONS` `Origin: https://evil.example.com` | **400**, sin cabeceras `access-control-*` | **PASA** |
| **AC-9** | `POST /eventos`; `GET /docs`, `/openapi.json`, `/redoc`, `/admin` | **405**, **404**, **404**, **404**, **404** | **PASA** |
| **AC-9** (Netlify) | Origen Netlify en preflight | `CORS_ORIGEN_NETLIFY` vacío en `.env` (solo localhost en vivo) | **NO VERIFICABLE** (cubierto en `test_api_rutas.py` / `test_config.py`) |
| **AC-1, AC-2** | Inserción/reenvío USGS en vivo | No ejecutado (tiempo; flujo consumidor) | **NO VERIFICABLE** (regresión en `test_ciclo.py` / ingestión 003) |
| **AC-3** | Evento `magnitud: null` en vivo | 0 magnitudes nulas en `live.evento_actual` | **NO VERIFICABLE** vivo (**PASA** en `test_calculos.py` / rutas) |
| **FR-007, AC-10** | Parar productor; API temporal umbral 60 s | Ver §3 | **PASA** |
| **FR-014, AC-11** | `docker compose stop postgres` | Ver §4 | **PASA** |
| **Solo lectura API** | `rg INSERT\|UPDATE\|DELETE\|CREATE\|DROP\|ALTER` en `backend/observatorio/api/` | **0 coincidencias**; SQL usa `{where}` + `%s` | **PASA** |
| **§10 rendimiento** | 15× curl por endpoint; `EXPLAIN ANALYZE` | Ver §5 | **PASA** |

---

## 3. AC-10 — productor parado

**Umbral por defecto en API principal:** 300 s (`/status` → `umbral_datos_desactualizados_segundos=300`).

1. Baseline con productor activo: `datos_desactualizados=false`, `ultima_ingesta_correcta=2026-11-02T16:09:29.522Z`.
2. `docker compose stop producer`.
3. Contenedor temporal (misma red Compose, **sin tocar `.env`**):

```powershell
docker compose run -d --name api-verif-ac10 --rm -p 127.0.0.1:8001:8000 -e DATOS_DESACTUALIZADOS_SEGUNDOS=60 api
Start-Sleep -Seconds 75
```

| Puerto | `datos_desactualizados` | Notas |
| --- | --- | --- |
| **8001** (umbral 60 s) | **true** | `ultima_ingesta_correcta` sin avanzar |
| **8000** (umbral 300 s) | **false** a ~75 s | Esperado: aún dentro de 300 s |

4. `docker compose start producer`; tras ~70 s y un ciclo USGS: ambos **false**, `ultima_ingesta_correcta=2026-11-02T16:12:14.690Z`.
5. `docker stop api-verif-ac10`.

**Veredicto AC-10:** **PASA** (lógica umbral + recuperación). No se esperaron 300 s en `:8000` con productor parado (alternativa documentada en enunciado de verificación).

---

## 4. AC-11 — PostgreSQL parado

Conteos antes: `live` **258**, `historico.evento_2025` **18302**.

```powershell
docker compose stop postgres
curl.exe -s http://127.0.0.1:8000/status
curl.exe -s http://127.0.0.1:8000/eventos
curl.exe -s http://127.0.0.1:8000/recuentos/pais
docker compose start postgres
# espera health + reconexión API (~6 s postgres + 5 s)
```

| Comprobación | Resultado |
| --- | --- |
| `/status` | **200**, `base_de_datos="fallida"`, campos de base **`null`** (incl. `datos_desactualizados`, `ultima_ingesta_correcta`, contadores) |
| `/eventos`, `/recuentos/pais` | **503**, cuerpo `{"error":"servicio_no_disponible"}` (sin SQL ni credenciales) |
| Productor / consumidor tras parada | Siguen **healthy** (reintentos) |
| Tras arranque postgres | API **sin reinicio** → `base_de_datos=conectada`; filas **258** / **18302** (persistencia OK) |

**Veredicto AC-11:** **PASA**.

---

## 5. Rendimiento (§10 / T10)

### 5.1 Latencia HTTP (15 peticiones, ~256 filas reales)

| Endpoint | Mediana (s) | Máximo (s) | Objetivo |
| --- | ---: | ---: | --- |
| `/eventos?limite=100` | 0.0047 | 0.0051 | ≤ 1 s |
| `/eventos/mapa` | 0.0065 | 0.0091 | ≤ 3 s (tope) |
| `/recuentos/pais` | 0.0030 | 0.0031 | ≤ 1 s |
| `/recuentos/hora` | 0.0032 | 0.0034 | ≤ 1 s |
| `/distribuciones/magnitud` | 0.0029 | 0.0032 | ≤ 1 s |
| `/comparacion-historica` | 0.0050 | 0.0053 | ≤ 3 s |

### 5.2 `EXPLAIN (ANALYZE, BUFFERS)` — tablas reales

- Lista top-100 (`live.evento_actual`, `NOT sintetico`): **Index Scan** `evento_actual_ocurrencia_idx`, **~0.07 ms**.
- Comparación denominador (`historico.evento_2025`, `magnitud >= 4`): seq scan 18.302 filas, **~1.96 ms**.

### 5.3 Esquema temporal `verif_tmp` (borrado al final)

```sql
DROP SCHEMA IF EXISTS verif_tmp CASCADE;
CREATE TABLE verif_tmp.evento_actual (LIKE live.evento_actual INCLUDING ALL);
-- 20.000 y 100.000 filas us7000verif*, sintetico=false, source=usgs
DROP SCHEMA verif_tmp CASCADE;
```

| Tamaño | Con índice `(ocurrencia DESC, event_id)` | Sin índice ocurrencia (+ sort) |
| --- | --- | --- |
| 20.000 | Index Scan, **~0.07 ms** | Otro índice copiado del LIKE; seq+sort **~2 ms** (poco representativo) |
| 100.000 | Index Scan, **~0.10 ms** | Parallel seq scan + sort, **~24 ms** |

Tras borrar `verif_tmp`: `live` **258**, `historico` **18302** (sin cambios por la carga sintética).

### 5.4 Pendiente menor T10

- **Espera de lock > 1 s** entre clientes concurrentes: no medida.
- **Tiempos HTTP** a 20k/100k: no aplicable sin sustituir tabla live (solo SQL en `verif_tmp`).

**Veredicto §10:** **PASA** objetivos locales; escalado validado por plan de consulta en 100k.

---

## 6. Seguridad ligera

| Comprobación | Resultado |
| --- | --- |
| `git grep -i -E "authtoken|password="` | Solo nombres de variable, tests ficticios y docs (sin credenciales reales) |
| `.env.example` | `POSTGRES_PASSWORD=` vacío |
| Respuesta `/status` | Sin password ni DSN |
| CORS | Orígenes exactos en código; preflight ajeno sin `access-control-*` |
| Puertos publicados | `127.0.0.1:8000`, `127.0.0.1:9092`; postgres **sin** puerto host |
| Montajes servicio `api` | Ninguno en `compose.yaml` |
| `git status` | Cambios esperados de la feature 005 (sin `.env` trackeado) |

---

## 7. Hallazgos (para developer)

| Gravedad | Hallazgo |
| --- | --- |
| **Informativo** | Conteo `live` sube con ingesta USGS durante la verificación (255→256→258 totales); usar rango `desde/hasta` para AC-7 estable. |
| **Informativo** | AC-10 en `:8000` con umbral **300 s** no demostrado hasta el minuto 5; la API en **8001** con 60 s sí lo demuestra. |
| **Informativo** | AC-9 origen Netlify solo en tests mientras `CORS_ORIGEN_NETLIFY` esté vacío (alineado con plan 006). |
| **Informativo** | Desviaciones del plan (`result=info` en log CORS, `SinCorsParaOrigenAjeno`, 500 vía middleware) coherentes con evidencias CORS/500. |
| **Bajo** | T10: falta medición explícita de contención del lock de conexión única bajo carga concurrente. |
| **Bajo** | `test_calculos.py` / enunciado AC-5 escenario «3 de 6 horas con eventos» no reproducido en datos USGS del día (sí en unitarios). |

---

## 8. Estado final de la pila

```text
docker compose ps → kafka, postgres, producer, consumer, api → healthy
```

Veredicto global: **PASA** (005-api lista para panel 006), con AC-1/2/3 y CORS Netlify no reproducidos en vivo pero cubiertos por tests o datos ausentes.
