# Observatorio de actividad sísmica

Proyecto de Sistemas de Big Data (sesiones 1–8, RA1). Recoge terremotos de
USGS, los transporta por Kafka, los valida y los cruza con el catálogo de
países de Natural Earth, los guarda en PostgreSQL y los sirve con FastAPI a un
panel Angular + Leaflet publicado en Netlify.

La pregunta que responde: **¿dónde se está registrando actividad sísmica y cómo
se compara con un periodo histórico equivalente?**

> Estado: Fase 0 (andamiaje). Los servicios se construyen feature a feature en
> `specs/`. El enunciado completo está en [docs/ENUNCIADO.md](docs/ENUNCIADO.md).

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

- Docker con Compose v2
- Node.js LTS (solo para compilar el frontend)
- Python 3.12+ (scripts de descarga y notebooks)
- Cuenta gratuita de ngrok y de Netlify (para la demostración)

## Arranque

```bash
cp .env.example .env   # en PowerShell: Copy-Item .env.example .env
docker compose up --build -d
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
| 001-esqueleto | Compose con los 5 servicios, healthchecks y esquema SQL |
| 002-ingesta-live | Productor USGS, estado de versiones publicadas, reintentos |
| 003-consumidor | Calidad, cuarentena, point-in-polygon, upsert por versión |
| 004-historico-replay | Descarga 2025 y reproducción acelerada aislada |
| 005-api | FastAPI, contrato, CORS |
| 006-panel | Angular + Leaflet, filtros, gráficos, Netlify + ngrok |
| 007-memoria | Calidad, rendimiento, costes y conclusiones |
