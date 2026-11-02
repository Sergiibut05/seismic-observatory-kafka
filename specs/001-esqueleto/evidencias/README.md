# Evidencias de verificación — feature 001-esqueleto

**Verificador**: subagente `verifier` (modo 2, post-implementación)  
**Rama**: `001-esqueleto` · commit base verificado: `101bc8d`  
**Fecha**: 2026-11-02 · Shell: PowerShell · Docker Compose v2  

Los comandos se ejecutaron desde la raíz del repositorio. La contraseña de `POSTGRES_PASSWORD` del `.env` local **no** se copia en este informe.

---

## 1. Pytest (quickstart §7)

**Comando**

```powershell
docker compose build
docker compose run --rm --no-deps consumer pytest -q
```

**Salida relevante**

```
361 passed in 2.17s
```

**Veredicto**: PASA  

**Fichero**: `pytest.txt` (misma salida).

---

## 2. SC-001 — Tres arranques desde cero (proyectos temporales)

**Comando** (resumen): `docker compose -p obsverif{N} down -v` → `up --build -d` → esperar 5× healthy → anotar tiempo → `down -v`. Proyecto principal parado durante cada prueba (puertos 8000/9092).

**Salida relevante** (`sc001-arranques.txt`)

| run | proyecto   | segundos | healthy |
| --- | ---------- | -------- | ------- |
| 1   | obsverif1  | 16,5     | True    |
| 2   | obsverif2  | 16,5     | True    |
| 3   | obsverif3  | 16,8     | True    |

**Veredicto**: PASA (≤ 120 s, 3/3 sin pasos manuales).

---

## 3. Quickstart §1 — Pila y arranque (SC-007, parte SC-001)

| #   | Comando / acción | Esperado | Resultado | Veredicto |
| --- | ---------------- | -------- | --------- | --------- |
| 1.1 | `docker ps` puertos | Solo `127.0.0.1:8000`, `127.0.0.1:9092` | api y kafka publicados; postgres `5432/tcp` sin bind | PASA |
| 1.2 | Esquemas SQL | ingesta, live, replay | 3 filas | PASA |
| 1.3 | Tablas | cuarentena, version_esquema, versiones_evento | 3 filas | PASA |
| 1.4 | `ingesta.version_esquema` | 1 / esquema_base | OK | PASA |
| 1.5 | Imagen Python | mismo sha256 | `sha256:55d6153227a14…` en producer, consumer, api | PASA |
| 1.6 | Sin `.env` / password vacía | error `POSTGRES_PASSWORD` | Mensaje «Falta POSTGRES_PASSWORD…» | PASA (`01-env-validation.txt`) |
| 1.8 | `/health`, `/status` | ok, 0/0 | `status: ok`, BD conectada | PASA |
| 1.9 | Log catálogo | paises=242 | `result=listo component=catalogo paises=242` | PASA |
| 1.10 | `/docs`, `/redoc`, `/openapi.json`, `/admin` | 404 | 404,404,404,404 | PASA |

**Ficheros**: `01-*.txt`, `01-health.json`, `01-status-inicial.json`.

---

## 4. Quickstart §2 — Humo e idempotencia

### 2.1 SC-002 — Visibilidad en API (3 repeticiones)

| run | segundos hasta `eventos_sinteticos=1` |
| --- | ------------------------------------- |
| 1   | 1,26                                  |
| 2   | 1,28                                  |
| 3   | 1,29                                  |

**Veredicto**: PASA (≤ 10 s).

### 2.2 SC-003 — Reenvío misma versión (§11)

- Tras `smoke --repeat 5`: `eventos_sinteticos=1`, `filas=1` en `live.versiones_evento`.
- 5 líneas `result=omitido … reason=duplicado` (`sc003-omitidos.txt`).

**Veredicto**: PASA.

### 2.3 SC-004 — Consumidor parado / reiniciado (§11)

- Con consumidor parado, `--unico` no aumenta recuento en API hasta arrancar consumidor.
- Tras `start`: sintéticos pasan de 1 → 2 (N+1).
- Tras `restart consumer`: sintéticos siguen en 2, `filas=2`.

**Veredicto**: PASA.

### 2.4 PostgreSQL caído con mensaje en vuelo

- Con postgres parado: partición 0 `LAG=1` (`024-lag-postgres-down.txt`).
- Tras recuperación: `LAG=0` en todas las particiones.

**Veredicto**: PASA.

### 2.5 FR-012 — Cuarentena

- Cuatro tipos de motivo presentes en BD: `json_ilegible`, `clave_distinta_de_id`, `mode_no_corresponde_al_topic`, `schema_version_no_soportada`.
- Total filas cuarentena=7 (acumulado de ejecuciones previas en volumen persistente; la prueba nueva añade los cuatro motivos).
- Tras `restart consumer`: recuento cuarentena sin cambio (`025-reentrega.txt`).
- `smoke --unico` tras cuarentena sigue funcionando.

**Veredicto**: PASA (motivos y no bloqueo); ver nota en § fallos menores.

### 2.6 SC-010 — Borrado de sintéticos

- Antes: `reales=1`, `sinteticos=4` (control insertado).
- Después de `borrar_sinteticos.sql`: `reales=1`, `sinteticos=0`.

**Veredicto**: PASA.

---

## 5. Enunciado §11 (aplicable a 001)

| Prueba | Acción | Antes → después | Veredicto |
| ------ | ------ | ----------------- | --------- |
| Recibir evento nuevo | `smoke` + GET `/status` | 0 → 1 sintético, `ultimo_evento.sintetico=true` | PASA (`s11-evento-nuevo-*.json/txt`) |
| Reenviar misma versión | `--repeat 5` | recuento 1, filas 1 | PASA |
| Reiniciar consumidor | `restart consumer` | recuento estable | PASA |

---

## 6. Quickstart §3 — SC-006

| Escenario | Cifra clave | Veredicto |
| --------- | ----------- | --------- |
| 3.1 Postgres tarde al arrancar | healthy consumer+api en 9,7 s | PASA |
| 3.3 Kafka tarde | healthy producer+consumer en 17 s | PASA |
| 3.4 Postgres cae en marcha | consumer+api `unhealthy`; `/status` `base_de_datos: fallida`, recuentos `null`; `/health` 503; recuperación ≤ 60 s | PASA |
| 3.5 Reinicio Kafka | healthy en 2,4 s; `smoke --unico` procesado | PASA |
| 3.6 Productor sin Kafka | `exit=1`, sin `result=publicado` | PASA |
| 3.7 Secretos en logs | coincidencias password=0, postgresql://=0 | PASA |

**Ficheros**: `sc006-*.txt`.

---

## 7. Quickstart §4 — SC-005

- Tras `down` / `up` sin `-v`: mismos recuentos e `event_id` (`sc005-antes.json` / `sc005-despues.json`; solo cambia `generated_at`).
- Retención por defecto: `retention.ms=604800000`, `segment.ms=86400000`.
- Cambio `TOPIC_RETENTION_MS=3600000`: `retention.ms=3600000`, `segment.ms=3600000`.
- Volúmenes nombrados `seismic-observatory_*` presentes.

**Veredicto**: PASA.

---

## 8. Quickstart §5 — SC-008

- Catálogo entregado: 242 países (`01-catalogo-log.txt`).
- Montaje solo lectura: «Read-only file system» (`sc008-catalogo-ro.txt`).
- Ausente: `motivo=catalogo_ausente` (`sc008-catalogo-ausente.txt`).
- Inválidos: cinco motivos esperados en logs (`sc008-catalogos-invalidos.txt`).

**Veredicto**: PASA (salud en contenedores efímeros quedó en `starting` a los 8–10 s; el error y motivo se registran en ≤ 30 s).

---

## 9. Quickstart §6 — SC-009, SC-011

| Comprobación | Resultado | Veredicto |
| ------------ | --------- | --------- |
| Formato logs Python | `total=26 invalidas=0` (muestra tras varios ciclos compose) | PASA* |
| Hash contrato ejemplo | `contract_hash_match=True` | PASA |
| `.env.example` password vacía | línea `POSTGRES_PASSWORD=` | PASA |
| `.env` en Git | no versionado | PASA |
| README `down -v` | presente | PASA (SC-011 documentación) |

\*SC-011 tiempo ≤ 15 min por persona nueva: **NO VERIFICABLE** en esta sesión automatizada; se comprobó que el README contiene puertos, listeners, arranque, humo, borrado sintéticos y `down -v`.

---

## 10. Seguridad (T060)

| Comprobación | Resultado | Veredicto |
| ------------ | --------- | --------- |
| Puertos publicados | 2 en 127.0.0.1 (8000, 9092) | PASA |
| PostgreSQL no publicado | solo `5432/tcp` | PASA |
| Rutas admin/docs | 404 | PASA |
| `git grep` secretos | Coincidencias solo en docs, tests con contraseñas ficticias y nombres de variable (`t060-git-grep.txt`) | PASA |
| Logs vs contraseña `.env` | 0 coincidencias | PASA |
| Ficheros contexto agente en repo | no encontrados | PASA |

---

## 11. Revisión de código crítico (solo lectura)

| Regla | Ubicación | Observación |
| ----- | --------- | ----------- |
| Offset tras commit PG | `consumer/app.py`: `procesar_con_reintentos` → `confirmar_offset` | PASA |
| Publicado tras acuse | `producer/smoke.py`: log tras `send_and_wait` | PASA |
| Idempotencia | `persistencia.py`: `ON CONFLICT (event_id, updated) DO NOTHING` | PASA |

---

## 12. Constitución v2.0.1 (alcance 001)

| Principio | Veredicto | Notas |
| --------- | --------- | ----- |
| I Reproducible Compose | PASA | 5 servicios, healthchecks, volúmenes, reintentos medidos |
| II Contrato v1 | PASA | Cuarentena por incumplimiento; tests contrato |
| III Offset / idempotencia | PASA | Evidencias §2 y revisión código |
| IV Trazabilidad/calidad | PASA (acotado) | Cuarentena con motivo; nulos no rellenados en skeleton |
| V Catálogo | PASA | Carga 242; validación motivos |
| VI Sintético / replay | PASA | Marca sintético; `mode=replay` rechazado en live |
| VII Superficie / secretos | PASA | Puertos, 404 docs, `.env` ignorado |
| VIII Simplicidad / evidencia | PASA | Stack acotado al enunciado |

---

## 13. Limpieza

- Proyectos `obsverif1..3`: eliminados con `down -v` (sin volúmenes/contenedores residuales).
- Proyecto principal: `docker compose down` **sin** `-v` al final (`cleanup-compose-down.txt`).

---

## 14. Hallazgos para el developer

1. **Menor — cuarentena acumulada**: en un volumen ya usado, `ingesta.cuarentena` puede tener más de 4 filas; conviene truncar o usar proyecto limpio en demos FR-012.
2. **Menor — SC-009 muestra pequeña**: tras muchos `down`, `docker compose logs` devolvió 26 líneas de servicios Python; `invalidas=0` en todas. Para auditoría estricta del 100 %, ejecutar §6.1 con la pila estable tras humo completo.
3. **Informativo — `git grep password=`**: aparecen tests (`test_db.py`) con cadenas ficticias; no son secretos reales (alineado con `research.md` T058).

No se detectaron fallos bloqueantes de criterios SC-001–SC-010.
