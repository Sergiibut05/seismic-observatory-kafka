# Quickstart y guía de validación: 001-esqueleto

Pasos **verificables** para el alumno y para el `verifier`. Todos los comandos son de
**PowerShell** desde la raíz del repositorio. Contratos: [contracts/](contracts/) ·
Modelo: [data-model.md](data-model.md) · Decisiones: [research.md](research.md).

> Guarda la salida de cada verificación en `specs/001-esqueleto/evidencias/` (lo hace el `verifier`).

## 0. Requisitos y preparación

- Docker con Compose v2 en marcha; puertos libres `127.0.0.1:8000` y `127.0.0.1:9092`.
- Acceso a internet en el primer arranque (descarga de imágenes y dependencias).

```powershell
Copy-Item .env.example .env
# Genera una contraseña aleatoria y la escribe en .env (no se imprime ni se sube a Git)
$pw = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
(Get-Content .env) -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$pw" | Set-Content .env
git check-ignore .env        # debe imprimir ".env" (ignorado por Git)
```

Funciones de ayuda para el resto del documento (pégalas en la sesión):

```powershell
# Ejecuta SQL dentro del contenedor de PostgreSQL (el SQL va por stdin: sin problemas de comillas)
function Invoke-Obs-Sql { param([Parameter(Mandatory)][string]$Sql)
  $Sql | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB' }
function Get-Obs-Status { Invoke-RestMethod http://127.0.0.1:8000/status | ConvertTo-Json -Depth 5 }
```

## 1. Levantar la pila (US1 · SC-001, SC-007)

```powershell
Measure-Command { docker compose up --build -d }
# Espera y comprueba el estado (máximo 120 s sin contar descargas)
docker compose ps --format "table {{.Service}}\t{{.Status}}"
```

**Esperado**: `kafka`, `postgres`, `producer`, `consumer` y `api` en `healthy` en ≤ 120 s, sin
intervención. Repetir el arranque desde cero **3 veces** (`docker compose down -v` entre medias)
y anotar los tiempos (SC-001).

| # | Comprobación | Orden | Esperado |
| --- | --- | --- | --- |
| 1.1 | Puertos publicados | `docker ps --format "{{.Names}}  {{.Ports}}"` | Solo `127.0.0.1:8000->8000/tcp` (api) y `127.0.0.1:9092->9092/tcp` (kafka); `postgres`, `producer` y `consumer` sin puertos (SC-007) |
| 1.2 | Esquemas e inicialización | `Invoke-Obs-Sql "SELECT nspname FROM pg_namespace WHERE nspname IN ('live','replay','ingesta') ORDER BY 1;"` | `ingesta`, `live`, `replay` |
| 1.3 | Tablas mínimas | `Invoke-Obs-Sql "\dt live.* ingesta.*"` | `live.versiones_evento`, `ingesta.cuarentena`, `ingesta.version_esquema` |
| 1.4 | Versión de esquema | `Invoke-Obs-Sql "SELECT * FROM ingesta.version_esquema;"` | Fila `1 / esquema_base` |
| 1.5 | Misma imagen en los tres servicios Python | `docker inspect --format "{{.Name}} {{.Image}} {{.Config.Cmd}}" (docker compose ps -q producer consumer api)` | Las tres líneas muestran el **mismo ID de imagen** (`sha256:…`); solo cambia el comando |
| 1.6 | Sin `.env` o sin contraseña | `Rename-Item .env .env.bak; docker compose config -q; Rename-Item .env.bak .env` | Error que nombra `POSTGRES_PASSWORD`. Repetir con `POSTGRES_PASSWORD=` vacía: mismo error |
| 1.7 | Sin contraseña por defecto en el código | `Select-String -Path compose.yaml,.env.example -Pattern 'POSTGRES_PASSWORD'` | `compose.yaml` usa `:?`; `.env.example` con valor vacío |
| 1.8 | Endpoints de la API | `Invoke-RestMethod http://127.0.0.1:8000/health; Get-Obs-Status` | `status: ok`; estado con `base_de_datos: conectada`, `eventos_reales: 0`, `eventos_sinteticos: 0`, `ultimo_evento: null` |
| 1.9 | Catálogo cargado (US5, sin mensajes aún) | `docker compose logs consumer --no-log-prefix \| Select-String 'component=catalogo'` | `result=listo component=catalogo paises=242 fuente=/catalogo/paises.geojson` en los primeros 30 s |
| 1.10 | Sin rutas de administración ni documentación | `foreach ($p in '/docs','/redoc','/openapi.json','/admin') { try { (Invoke-WebRequest "http://127.0.0.1:8000$p" -UseBasicParsing).StatusCode } catch { $_.Exception.Response.StatusCode.value__ } }` | `404` en todas |

Conflicto de puertos: si el arranque falla con «port is already allocated», identifica al
proceso con `Get-NetTCPConnection -LocalPort 8000,9092 | Select-Object LocalPort, OwningProcess` y
`Get-Process -Id <PID>`.

## 2. Prueba de humo (US2 · SC-002, SC-003, SC-004, SC-010)

### 2.1 Publicar y ver el evento (SC-002)

```powershell
docker compose exec producer python -m observatorio.producer.smoke
Start-Sleep -Seconds 3
Get-Obs-Status
docker compose logs producer consumer api --no-log-prefix --since 2m
```

**Esperado**: el log del productor muestra `result=publicado event_id=synthetic-smoke-0001 updated=1767225600000 …`
**solo después** del acuse; el del consumidor `result=persistido …`; la API informa
`eventos_sinteticos: 1`, `eventos_reales: 0` y `ultimo_evento.sintetico: true` en ≤ 10 s.
Repetir 3 veces borrando antes los sintéticos (§2.6) y anotar el tiempo entre publicación y visibilidad.

### 2.2 Reenvío de la misma versión (SC-003)

```powershell
docker compose exec producer python -m observatorio.producer.smoke --repeat 5
Start-Sleep -Seconds 3
Get-Obs-Status
Invoke-Obs-Sql "SELECT count(*) AS filas FROM live.versiones_evento;"
docker compose logs consumer --no-log-prefix --since 1m | Select-String 'result=omitido'
```

**Esperado**: `eventos_sinteticos` sigue en `1`, `filas = 1`, y 5 líneas `result=omitido … reason=duplicado`
con el mismo `event_id` y `updated`.

### 2.3 Consumidor detenido y reiniciado (SC-004)

```powershell
Invoke-Obs-Sql "SELECT count(*) FROM live.versiones_evento;"                # anota N
docker compose stop consumer
docker compose exec producer python -m observatorio.producer.smoke --unico  # evento nuevo
Get-Obs-Status                                                              # aún N (no se procesó)
docker compose start consumer
Start-Sleep -Seconds 15
Get-Obs-Status                                                              # N + 1 evento, exactamente
docker compose restart consumer
Start-Sleep -Seconds 15
Get-Obs-Status                                                              # sigue en N + 1
docker compose logs consumer --no-log-prefix --since 1m | Select-String 'result=(persistido|omitido)'
```

**Esperado**: el evento publicado con el consumidor parado se procesa **una sola vez**; tras el
reinicio no hay efecto visible (0 pérdidas, 0 duplicados).

### 2.4 Caída de PostgreSQL con mensaje en vuelo (US2 escenario 4)

```powershell
docker compose stop postgres
docker compose exec producer python -m observatorio.producer.smoke --unico
Start-Sleep -Seconds 10
# El offset NO se ha confirmado: el grupo muestra retraso (LAG) >= 1
docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group consumidor-live
docker compose logs consumer --no-log-prefix --since 1m | Select-String 'result=(reintento|error)'
docker compose start postgres
Start-Sleep -Seconds 45
docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group consumidor-live
Get-Obs-Status
```

**Esperado**: con PostgreSQL parado, `LAG ≥ 1` y reintentos del **mismo** mensaje; al volver, el
mensaje se persiste **exactamente una vez** y el `LAG` baja a 0.

### 2.5 Mensajes que incumplen el contrato → cuarentena (FR-012)

Cada línea es `clave|valor` (separador `|`). Usa un topic live real: `eventos.live`.

```powershell
# JSON ilegible
'k1|{esto no es json' | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:19092 --topic eventos.live --property parse.key=true --property key.separator='|'
# Clave distinta del id
'otra|{"schema_version":1,"source":"usgs","ingested_at":"2026-11-02T12:00:00.000Z","mode":"live","event":{"id":"us1","properties":{"updated":1767225600000}}}' | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:19092 --topic eventos.live --property parse.key=true --property key.separator='|'
# mode=replay en el topic live
'us2|{"schema_version":1,"source":"usgs","ingested_at":"2026-11-02T12:00:00.000Z","mode":"replay","event":{"id":"us2","properties":{"updated":1767225600000}}}' | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:19092 --topic eventos.live --property parse.key=true --property key.separator='|'
# schema_version no soportada
'us3|{"schema_version":2,"source":"usgs","ingested_at":"2026-11-02T12:00:00.000Z","mode":"live","event":{"id":"us3","properties":{"updated":1767225600000}}}' | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:19092 --topic eventos.live --property parse.key=true --property key.separator='|'
Start-Sleep -Seconds 5
Invoke-Obs-Sql "SELECT motivo, detalle, topic, particion, offset_kafka, convert_from(original,'UTF8') AS original FROM ingesta.cuarentena ORDER BY id;"
docker compose logs consumer --no-log-prefix --since 1m | Select-String 'result=rechazado'
Get-Obs-Status   # los recuentos de eventos no cambian
```

**Esperado**: 4 filas con motivos `json_ilegible`, `clave_distinta_de_id`,
`mode_no_corresponde_al_topic`, `schema_version_no_soportada`; 4 líneas `result=rechazado`; el consumidor
**no se bloquea** (publicar después `smoke --unico` sigue funcionando). Reentrega: `docker compose restart consumer`
y repetir la consulta: el recuento de filas de cuarentena no varía (`UNIQUE (topic, particion, offset_kafka)`).
(Un `\u0000` dentro de un string de un mensaje válido debe acabar como `no_almacenable`; ver prueba unitaria.)

### 2.6 Eliminar solo los sintéticos (SC-010, FR-019)

```powershell
# Antes: inserta un "real" de control (como lo haría la 002) para comprobar que no se toca
Invoke-Obs-Sql @"
INSERT INTO live.versiones_evento (event_id, updated, schema_version, source, sintetico, ingested_at, topic, particion, offset_kafka, original)
VALUES ('us-control-0001', '2026-01-01T00:00:00Z', 1, 'usgs', false, now(), 'control', 0, 0, '{}'::jsonb);
"@
Get-Obs-Status       # eventos_reales: 1
Get-Content -Raw scripts/borrar_sinteticos.sql | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB'
Get-Obs-Status       # eventos_sinteticos: 0, eventos_reales: 1 (sin cambios)
# Limpieza del control (es un dato de prueba creado a mano, no sintético)
Invoke-Obs-Sql "DELETE FROM live.versiones_evento WHERE event_id = 'us-control-0001';"
docker compose exec producer python -m observatorio.producer.smoke   # recrea el sintético
```

**Esperado**: `eventos_sinteticos` pasa a 0, `eventos_reales` se mantiene en 1 y **en ningún momento** el
sintético aparece en `eventos_reales`. Publicar de nuevo lo recrea (idempotencia ≠ imposibilidad de recrear).

## 3. Dependencias lentas o caídas (US3 · SC-006)

| # | Escenario | Orden | Esperado |
| --- | --- | --- | --- |
| 3.1 | PostgreSQL parado al arrancar | `docker compose down; docker compose up -d --no-deps kafka producer consumer api` y mirar `docker compose ps` y `docker compose logs consumer api --no-log-prefix` | `consumer` y `api` **no salen**; líneas `result=reintento dependency=postgres attempt=N wait_s=…` con espera creciente 1, 2, 4, 8, 16, 30, 30 s; estado `starting`/`unhealthy` |
| 3.2 | PostgreSQL llega tarde | `docker compose up -d postgres` | `consumer` y `api` pasan a `healthy` ≤ 60 s después; `docker inspect --format "{{.RestartCount}}" <contenedores>` = `0` |
| 3.3 | Kafka parado al arrancar | `docker compose down; docker compose up -d --no-deps postgres producer consumer api`, luego `docker compose up -d kafka` | Igual con `dependency=kafka`; `healthy` ≤ 60 s tras Kafka; el consumidor registra `reason=topic_no_existe` hasta que el productor crea el topic |
| 3.4 | PostgreSQL cae en marcha | `docker compose stop postgres; Start-Sleep 60; docker compose ps; Get-Obs-Status; Invoke-RestMethod http://127.0.0.1:8000/health` | `consumer` y `api` `unhealthy` ≤ 60 s; `/status` → `base_de_datos: fallida` con recuentos `null` (no 0); `/health` → 503. Al hacer `docker compose start postgres`, vuelven a `healthy` ≤ 60 s sin reiniciar contenedores |
| 3.5 | Kafka se reinicia en marcha | `docker compose restart kafka; Start-Sleep 60; docker compose ps` y luego `smoke --unico` | `producer` y `consumer` recuperan `healthy` ≤ 60 s y el evento nuevo se procesa (valida RK-01) |
| 3.6 | Productor sin acuse (FR-014) | `docker compose stop kafka; docker compose exec producer python -m observatorio.producer.smoke; echo "exit=$LASTEXITCODE"` | `result=error` tras `SMOKE_TIMEOUT_SECONDS`, **sin** `result=publicado`, código de salida ≠ 0 |
| 3.7 | Sin secretos en logs | `docker compose logs --no-log-prefix \| Select-String -SimpleMatch $pw` y `... \| Select-String 'postgresql://\|password='` | Sin coincidencias |

## 4. Persistencia y retención (US4 · SC-005)

```powershell
docker compose up -d
docker compose exec producer python -m observatorio.producer.smoke
Start-Sleep -Seconds 5
Get-Obs-Status > antes.json   # (guardar en evidencias/, no en Git)
docker compose down           # SIN -v
docker compose up -d
Start-Sleep -Seconds 60
Get-Obs-Status > despues.json
Compare-Object (Get-Content antes.json) (Get-Content despues.json)   # solo debe diferir generated_at
# El mensaje sigue leíble en el topic (la retención no ha vencido)
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic eventos.live --from-beginning --max-messages 1 --timeout-ms 15000
```

| # | Comprobación | Orden | Esperado |
| --- | --- | --- | --- |
| 4.1 | Propietario del volumen de Kafka | `docker compose exec kafka ls -ld /var/lib/kafka/data` | Pertenece a `appuser` (R-03); Kafka escribe sin `Permission denied` |
| 4.2 | Datos de Kafka no en `/tmp` | `docker compose exec kafka ls /var/lib/kafka/data` | Contiene `eventos.live-0…2`, `__consumer_offsets-*`, `meta.properties` |
| 4.3 | Retención efectiva | `docker compose exec kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka:19092 --entity-type topics --entity-name eventos.live --describe` | `retention.ms=604800000` y `segment.ms=86400000` (finitos) |
| 4.4 | Cambiar retención por variable | En `.env`: `TOPIC_RETENTION_MS=3600000`; `docker compose up -d producer`; esperar 20 s; repetir 4.3 | `retention.ms=3600000` y `segment.ms=3600000` (log `action=topic_reconciliado`); `compose.yaml` sin tocar. Restaurar 604800000 después |
| 4.5 | Volúmenes con nombre | `docker volume ls --filter name=seismic-observatory` | `…_kafka_data` y `…_postgres_data` |
| 4.6 | Borrado total, única orden | README | Indica que `docker compose down -v` es la única orden que borra datos |

## 5. Catálogo de países (US5 · SC-008)

```powershell
# 5.1 Catálogo entregado
docker compose logs consumer --no-log-prefix | Select-String 'component=catalogo'      # paises=242 fuente=/catalogo/paises.geojson, en los primeros 30 s
# 5.2 Solo lectura
docker compose exec consumer sh -c "touch /catalogo/prueba"                              # "Read-only file system"
# 5.3 Catálogo ausente
docker compose run --rm --no-deps -d --name consumer-sin-catalogo -e CATALOGO_PATH=/catalogo/no_existe.geojson consumer
Start-Sleep -Seconds 10
docker logs consumer-sin-catalogo | Select-String 'motivo='                              # motivo=catalogo_ausente + ruta esperada
docker inspect --format "{{.State.Health.Status}}" consumer-sin-catalogo                 # starting -> unhealthy (nunca healthy)
docker rm -f consumer-sin-catalogo
```

Catálogos inválidos (ficheros en `data/`, ignorado por Git):

```powershell
New-Item -ItemType Directory -Force data/catalogos-prueba | Out-Null
Set-Content data/catalogos-prueba/ilegible.geojson '{no es json'
Set-Content data/catalogos-prueba/vacio.geojson '{"type":"FeatureCollection","features":[]}'
Set-Content data/catalogos-prueba/punto.geojson '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"ADM0_A3":"AAA"},"geometry":{"type":"Point","coordinates":[0,0]}}]}'
Set-Content data/catalogos-prueba/sin_adm0.geojson '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}}]}'
Set-Content data/catalogos-prueba/repetido.geojson '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"ADM0_A3":"AAA"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}},{"type":"Feature","properties":{"ADM0_A3":"AAA"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}}]}'
foreach ($f in 'ilegible','vacio','punto','sin_adm0','repetido') {
  docker compose run --rm --no-deps -d --name "consumer-cat-$f" -v "${PWD}/data/catalogos-prueba:/cat-prueba:ro" -e "CATALOGO_PATH=/cat-prueba/$f.geojson" consumer | Out-Null
  Start-Sleep -Seconds 8
  "== $f"; docker logs "consumer-cat-$f" | Select-String 'motivo='
  docker rm -f "consumer-cat-$f" | Out-Null
}
```

**Esperado**: motivos `catalogo_ilegible`, `catalogo_vacio`, `geometria_no_poligonal`, `adm0_a3_ausente`,
`adm0_a3_repetido` respectivamente; en todos, ningún `result=persistido/omitido/rechazado` y salud
no sana. (Si algún nombre de contenedor queda huérfano: `docker rm -f consumer-cat-<nombre>`.)

## 6. Logs, configuración y documentación (US6 · SC-009, SC-011)

```powershell
# 6.1 El 100 % de las líneas cumple el formato (SC-009)
$rx = '^(\S+\s+\|\s+)?ts=\S+ level=\S+ service=(producer|consumer|api) result=\S+( .*)?$'
$lineas = docker compose logs --no-color | Where-Object { $_ -match '^(producer|consumer|api)-1' }
"total=$($lineas.Count) invalidas=$(($lineas | Where-Object { $_ -notmatch $rx }).Count)"       # invalidas=0
# 6.2 Líneas de evento con event_id y updated
docker compose logs --no-log-prefix | Select-String 'result=(publicado|persistido|omitido|rechazado)' | Select-String -NotMatch 'event_id=\S+ .*updated=\S+'   # sin salida
# 6.3 .env.example enumera todas las variables y no contiene credenciales
Select-String -Path .env.example -Pattern '^(POSTGRES_PASSWORD)=$'                               # contraseña vacía
git ls-files .env                                                                                # sin salida (.env no versionado)
# 6.4 El contrato de ejemplo está sincronizado con la copia de pruebas
(Get-FileHash specs/001-esqueleto/contracts/mensaje-kafka-v1.ejemplo.json).Hash -eq (Get-FileHash backend/tests/fixtures/mensaje_v1_ejemplo.json).Hash   # True
```

**6.5 Documentación (SC-011)**: una persona que no escribió la pila sigue solo el apartado «Puertos,
listeners y arranque» del `README.md` y consigue levantar la pila, ejecutar la prueba de humo y
eliminar el sintético en ≤ 15 min (cronometrar sin contar descargas). El apartado debe contener:
puertos publicados y finalidad, listeners (`kafka:19092` interno, `localhost:9092` host),
arranque/parada, reinicio sin pérdida, `down -v`, retención por defecto, prueba de humo, eliminación
de sintéticos, aplicar esquema a un volumen existente y conflicto de puertos.

## 7. Pruebas unitarias (en la imagen, Python 3.12)

```powershell
docker compose run --rm --no-deps consumer pytest -q
```

**Esperado**: todas en verde sin Kafka ni PostgreSQL en marcha. Cubren: contrato v1 (cada motivo de
rechazo), backoff, formato `clave=valor` y redacción de secretos, validación del catálogo, decisión del
consumidor (persistido/omitido/rechazado/no almacenable), configuración, estado de salud, reglas de
`ensure_topic`, evento sintético, estado de la API y supervisor.

## 8. Trazabilidad de las verificaciones

| Éxito | Verificación | Prueba del enunciado §11 |
| --- | --- | --- |
| SC-001 | §1 (3 arranques desde cero) | — |
| SC-002 | §2.1 | «Recibir un evento nuevo» (sintético) |
| SC-003 | §2.2 | «Reenviar la misma versión» |
| SC-004 | §2.3 | «Reiniciar consumidor» |
| SC-005 | §4 | — |
| SC-006 | §3.1–3.5 | — |
| SC-007 | §1.1 | — |
| SC-008 | §5 | — |
| SC-009 | §6.1, §3.7 | — |
| SC-010 | §2.6 | — |
| SC-011 | §6.5 | — |
| FR-012 | §2.5 | — |
| FR-014 | §3.6 | — |

## 9. Limpieza

```powershell
docker compose down          # conserva datos
docker compose down -v       # BORRA los volúmenes (única orden que elimina los datos)
Remove-Item -Recurse -Force data/catalogos-prueba, antes.json, despues.json -ErrorAction SilentlyContinue
```
