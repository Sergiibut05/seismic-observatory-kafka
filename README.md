# Observatorio de actividad sísmica

Proyecto de Sistemas de Big Data (sesiones 1–8, RA1). Recoge terremotos de
USGS, los transporta por Kafka, los valida y los cruza con el catálogo de
países de Natural Earth, los guarda en PostgreSQL y los sirve con FastAPI a un
panel Angular + Leaflet publicado en Netlify.

La pregunta que responde: **¿dónde se está registrando actividad sísmica y cómo
se compara con un periodo histórico equivalente?**

> Estado: feature `002-ingesta-live`. El productor consulta USGS cada 60 s.
> El histórico, la API analítica y el panel llegan en las features 004–006.

## Arquitectura

```text
USGS all_day.geojson ─► producer ─┐
                                  ├─► kafka ─► consumer ─► postgres ─► api ─► ngrok (HTTPS) ─► Angular (Netlify)
histórico 2025 ──────► replay ────┘                ▲
                                     paises.geojson (Natural Earth)
```

| Servicio | Tecnología | Papel |
| --- | --- | --- |
| `producer` | Python + aiokafka | Consulta USGS cada 60 s y publica eventos nuevos o revisados |
| `kafka` | Apache Kafka 4.1 (KRaft) | Transporte y retención de mensajes |
| `consumer` | Python + aiokafka | Validación, cuarentena, integración geográfica y escritura idempotente |
| `postgres` | PostgreSQL | Estado actual, historial de versiones, originales y estado de ingesta |
| `api` | FastAPI | Consulta de datos ya procesados; único servicio expuesto por el túnel |

## Requisitos

- Docker con Compose v2 (puertos 8000 y 9092 libres en 127.0.0.1)
- Node.js LTS (solo para compilar el frontend)
- Python 3.12+ (scripts de descarga y notebooks)
- Cuenta gratuita de ngrok y de Netlify (para la demostración)

## Puertos, listeners y arranque

Todas las órdenes son de **PowerShell** y se ejecutan desde la raíz del repositorio.

### Puertos publicados

| Puerto en el anfitrión | Servicio | Para qué |
| --- | --- | --- |
| `127.0.0.1:8000` | `api` | `GET /health` y `GET /status` (el túnel ngrok apuntará aquí) |
| `127.0.0.1:9092` | `kafka` | Solo inspección desde el anfitrión (listener `HOST`) |

PostgreSQL (`5432`) **no** se publica: solo es accesible dentro de la red de Compose. Tampoco se publican los
puertos de salud internos (`8081` en productor y consumidor). `docker ps` puede mostrar `5432/tcp` en `postgres`:
es el puerto que la imagen **expone**, no uno publicado; solo los que llevan `127.0.0.1:…->` lo están.

### Listeners de Kafka

| Listener | Dirección | Úsalo desde |
| --- | --- | --- |
| `INTERNAL` | `kafka:19092` | Otros contenedores (productor, consumidor) y órdenes con `docker compose exec` |
| `HOST` | `localhost:9092` | Herramientas del anfitrión (inspección) |

Dentro de Compose usa siempre el nombre del servicio (`kafka:19092`, `postgres:5432`), nunca `localhost`.

### Arranque

```powershell
Copy-Item .env.example .env
# Define POSTGRES_PASSWORD (aquí, una aleatoria) y guarda .env en UTF-8 sin BOM. No se sube a Git.
$pw = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
$texto = [IO.File]::ReadAllText("$PWD\.env") -replace '(?m)^POSTGRES_PASSWORD=[^\r\n]*', "POSTGRES_PASSWORD=$pw"
[IO.File]::WriteAllText("$PWD\.env", $texto, (New-Object Text.UTF8Encoding($false)))
git check-ignore .env                 # debe imprimir ".env"

docker compose up --build -d
docker compose ps                     # los cinco servicios en "healthy" en ≈ 2 minutos
Invoke-RestMethod http://127.0.0.1:8000/status
```

El orden de arranque no está garantizado ni hace falta: cada servicio reintenta con backoff (1, 2, 4, 8, 16, 30 s…)
hasta que su dependencia responde, sin reiniciar el contenedor. Toda orden de `docker compose` exige
`POSTGRES_PASSWORD` en `.env` (sin él, Compose falla nombrando la variable).

### Parada, reinicio y borrado

```powershell
docker compose down        # para y elimina los contenedores; los datos se conservan
docker compose up -d       # vuelve a arrancar con los mismos datos
```

**`docker compose down -v` es la única orden que borra datos** (volúmenes `kafka_data` y `postgres_data`).

### Retención de Kafka

El topic `eventos.live` conserva los mensajes **7 días** por defecto (`TOPIC_RETENTION_MS=604800000`). Para
cambiarla, edita `TOPIC_RETENTION_MS` en `.env` y recrea el productor: `docker compose up -d producer`. Reconcilia el
topic existente (`action=topic_reconciliado` en el log); no hace falta tocar `compose.yaml`.

### Prueba de humo

Publica un evento sintético (`synthetic-smoke-0001`) con acuse de Kafka y el consumidor lo guarda:

```powershell
docker compose exec producer python -m observatorio.producer.smoke              # una vez
docker compose exec producer python -m observatorio.producer.smoke --repeat 5   # la misma versión 5 veces: se omite como duplicado
docker compose exec producer python -m observatorio.producer.smoke --unico      # otro evento sintético distinto
Invoke-RestMethod http://127.0.0.1:8000/status                                  # eventos_sinteticos
```

### Ingesta USGS

Con la pila en marcha el productor descarga solo el feed de las últimas 24 h
(`USGS_FEED_URL`, cada `POLL_INTERVAL_SECONDS`). Publica los terremotos nuevos
o revisados; si la misma versión ya tuvo acuse, el log dice `result=omitido`.

```powershell
docker compose logs producer --since 2m
Invoke-RestMethod http://127.0.0.1:8000/status    # eventos_reales sube tras el primer ciclo
```

El GeoJSON original queda en `data/usgs/` (no se sube a Git). Una respuesta
idéntica a la anterior no genera otra copia. Lo más viejo de
`FEED_RETENTION_HOURS` (48 h) se borra. Cada consulta queda en
`ingesta.consultas` y lo que no es `earthquake`, en `ingesta.exclusiones`.

Que un evento deje de salir en el feed no lo borra: puede haber cumplido 24 h.
Tampoco se reconcilian aquí los que USGS elimine o fusione fuera de la ventana.
Si el productor estuvo parado más de 24 h, ese hueco se recupera con el
catálogo FDSN (feature 004), no releyendo `all_day`.

Eliminar solo los datos sintéticos (los reales no se tocan):

```powershell
Get-Content -Raw scripts/borrar_sinteticos.sql | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB'
```

### Esquema de PostgreSQL en un volumen existente

`db/init/*.sql` solo se ejecuta sobre un volumen **vacío**. Los ficheros son idempotentes: para aplicar un cambio
de esquema sin perder datos (ver [research.md R-07](specs/001-esqueleto/research.md#r-07--evolución-del-esquema-sobre-volúmenes-existentes)):

```powershell
docker compose exec postgres sh -c 'for f in /docker-entrypoint-initdb.d/*.sql; do psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB -f $f || exit 1; done'
```

### Pruebas

Se ejecutan dentro de la imagen (Python 3.12), sin Kafka ni PostgreSQL:

```powershell
docker compose run --rm --no-deps consumer pytest -q
```

### Si un puerto está ocupado

Si `docker compose up` falla con «port is already allocated», busca quién usa el puerto y detenlo:

```powershell
Get-NetTCPConnection -LocalPort 8000,9092 -State Listen | Select-Object LocalPort, OwningProcess
Get-Process -Id <OwningProcess>
```
## Datos de partida

- Catálogo geográfico: `catalogo/paises.geojson` (Natural Earth Admin 0
  1:50m, 242 países, versionado en Git). Se regenera con
  `python scripts/descargar_paises.py`, que valida `ADM0_A3`, geometrías y CRS
  y escribe su huella en `catalogo/paises.manifest.json`. Véase
  [docs/FUENTES-Y-LICENCIAS.md](docs/FUENTES-Y-LICENCIAS.md).
- Histórico 2025: se añade en la feature 004.

## Cómo se desarrolla

El proyecto sigue Spec-Driven Development con
[GitHub Spec Kit](https://github.com/github/spec-kit) y cuatro subagentes de
Cursor (`analyst`, `architect`, `developer`, `verifier`) definidos en
`.cursor/agents/`. Cada feature vive en `specs/NNN-nombre/`:

| Feature | Alcance |
| --- | --- |
| 001-esqueleto | **Hecha.** Compose con los 5 servicios, healthchecks, esquema SQL, prueba de humo y recuperación ante caídas |
| 002-ingesta-live | **Hecha.** Productor USGS, estado de versiones publicadas, reintentos |
| 003-consumidor | Calidad, cuarentena, point-in-polygon, upsert por versión |
| 004-historico-replay | Descarga 2025 y reproducción acelerada aislada |
| 005-api | FastAPI, contrato, CORS |
| 006-panel | Angular + Leaflet, filtros, gráficos, Netlify + ngrok |
| 007-memoria | Calidad, rendimiento, costes y conclusiones |
