# Fuentes, licencias y huella del catálogo

Registro de procedencia de los datos y componentes de terceros. Sustituye al
`FUENTES-Y-LICENCIAS.md` que el enunciado (apartado 3) da por entregado y que
no se ha proporcionado.

## Datos

| Fuente | Uso en el proyecto | Acceso | Licencia y atribución |
| --- | --- | --- | --- |
| USGS Earthquake Hazards Program: feed `all_day.geojson` | Datos recientes (ventana móvil de 24 h), consultados cada 60 s por `producer` | <https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson> | Dominio público (EE. UU.). Se cita «Fuente: U.S. Geological Survey». |
| USGS FDSN Event Web Service | Histórico 2025, magnitud ≥ 4, `eventtype=earthquake` (feature 004) | <https://earthquake.usgs.gov/fdsnws/event/1/> | Dominio público (EE. UU.). Las consultas se registran en el manifiesto del histórico. |
| Natural Earth: Admin 0 Countries 1:50m | Catálogo geográfico: punto en polígono en `consumer` y fronteras del mapa | Etiqueta `v5.1.2` de [nvkelso/natural-earth-vector](https://github.com/nvkelso/natural-earth-vector) | Dominio público. «Made with Natural Earth». |

## Catálogo geográfico entregado en el repositorio

`catalogo/paises.geojson` se genera con:

```bash
python scripts/descargar_paises.py
```

El script descarga la versión fijada, valida y escribe
`catalogo/paises.manifest.json` con todas las comprobaciones. Huella de la
extracción actual (2026-11-02T11:48:43Z):

| | SHA-256 | Bytes |
| --- | --- | --- |
| Fuente `ne_50m_admin_0_countries.geojson` (v5.1.2) | `3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb` | 3 083 490 |
| Resultado `catalogo/paises.geojson` | `94e49353da973273d9450ff7c350ffb0ff1b7a4e72139475712d09a71f636af6` | 2 306 248 |

Transformación aplicada: ninguna sobre geometrías ni orden. Solo se eliminan
atributos que el proyecto no usa; se conservan `ADM0_A3`, `NAME_ES`, `ADMIN`,
`CONTINENT`, `SUBREGION`, `REGION_UN`, `ISO_A3` y `TYPE`.

Resultado de las comprobaciones:

- 242 entidades, todas `Polygon` o `MultiPolygon`, coordenadas finitas dentro
  de [-180, 180] × [-90, 90].
- CRS declarado `urn:ogc:def:crs:OGC:1.3:CRS84`, equivalente a EPSG:4326 con
  orden longitud, latitud, el mismo que usa USGS.
- Ningún atributo obligatorio vacío.
- `ADM0_A3` único en las 242 entidades: se usa como clave del catálogo.
- 12 entidades con `ADM0_A3` distinto de `ISO_A3`: `ALD`, `ATC`, `CYN`, `FRA`,
  `IOA`, `KAS`, `KOS`, `NOR`, `PSX`, `SAH`, `SDS` y `SOL`. Confirma que
  `ADM0_A3` no debe tratarse como código ISO oficial.
- Validez topológica con Shapely: 0 geometrías inválidas.

Limitaciones conocidas: a escala 1:50m las costas están simplificadas, de modo
que un epicentro muy próximo a la costa puede caer en el mar o en tierra según
la simplificación. Ese caso se clasifica como «Sin país asignado» y no como
error (enunciado, 4.3). Los límites de Natural Earth reflejan su criterio
editorial de facto y no una posición oficial sobre territorios en disputa.

## Componentes de software

| Componente | Uso | Licencia |
| --- | --- | --- |
| Apache Kafka 4.1 (`apache/kafka`) | Broker | Apache 2.0 |
| PostgreSQL | Almacenamiento | PostgreSQL License |
| aiokafka, FastAPI, Uvicorn, Shapely | Backend Python | Apache 2.0, MIT, BSD-3, BSD-3 |
| Angular | Panel | MIT |
| Leaflet | Mapa | BSD-2-Clause |
| Teselas de fondo (se decide en la feature 006: OpenStreetMap o CARTO) | Fondo del mapa | OSM: ODbL, atribución «© OpenStreetMap contributors» y política de uso de teselas. CARTO: atribución «© CARTO» y límites de su plan gratuito. |

## Datos ficticios y sintéticos

Cualquier evento ficticio (demo del mapa sin backend), caso dañado a propósito
o réplica para pruebas de escala se guarda marcado como sintético y fuera del
análisis real (constitución, principio VI). Se listarán aquí con su ubicación
cuando se creen.
