# Comandos de apoyo de la memoria

Las cifras que no salen de PostgreSQL (`consultas.sql`, `Qnn`) ni de `mediciones.md` salen de estos comandos, `Cnn` en
la memoria. Todos se ejecutaron el **2026-11-08** en PowerShell, desde la raíz del repositorio, con la pila en
marcha, entre las 14:08 y las 14:16 UTC. Es lo que devolvieron ese día, copiado tal cual: USGS y Docker cambian, y
al repetirlos saldrán otras cifras (salvo `C1`, que lee ficheros que no cambian).

## C1 · Procedencia del histórico y del catálogo (ficheros fuera de Git)

```powershell
$m = Get-Content data\historico\2025\manifest.json -Raw -Encoding utf8 | ConvertFrom-Json
"extracted_at=$($m.extracted_at) eventos=$($m.eventos) duplicados=$($m.duplicados_de_extremo) consultas=$($m.consultas.Count)"
($m.consultas | Measure-Object bytes -Sum).Sum
$m.consultas | ForEach-Object { "{0} {1}" -f $_.inicio.Substring(0,7), $_.features }
(Get-FileHash catalogo\paises.geojson -Algorithm SHA256).Hash
Get-Content catalogo\paises.manifest.json -Raw -Encoding utf8 | ConvertFrom-Json
Get-Item data\historico\2025\eventos.geojson, data\historico\2025\manifest.json | Select-Object Name, Length
```

Resultado: `extracted_at=2026-11-02T15:17:20Z`, `eventos=18302`, `duplicados_de_extremo=0`, 12 consultas (todas HTTP 200,
13.011.906 bytes en total). Eventos por mes (suma 18.302): 2025-01 1.413, 02 1.394, 03 1.178, 04 1.316, 05 1.228,
06 1.156, 07 2.684, 08 2.222, 09 1.604, 10 1.509, 11 1.321, 12 1.277. Ningún mes llegó al tope de 20.000: no hubo
que partir intervalos. `eventos.geojson`: 12.988.889 bytes; `manifest.json`: 4.701 bytes. Catálogo
`paises.geojson`: 2.306.248 bytes, 242 entidades, Natural Earth v5.1.2, extraído el 2026-11-02T11:48:43+00:00,
SHA-256 `94e49353da973273d9450ff7c350ffb0ff1b7a4e72139475712d09a71f636af6` (coincide con el del manifiesto).

## C2 · Equipo anfitrión (Windows)

```powershell
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, Size
docker version --format '{{.Server.Version}} / client {{.Client.Version}}'
```

Resultado: AMD Ryzen 5 7600X, 6 núcleos y 12 hilos, 4.701 MHz máximos; placa MSI MS-7E24; 33.328.848.896 bytes
de RAM (31,04 GiB); Windows 11 Pro 10.0.26200; discos KIOXIA EXCERIA PLUS G3 (SSD, 2 TB) y ST4000VN006-3CW104 (HDD, 4 TB);
Docker 27.5.1 (servidor y cliente). Desde dentro del contenedor (WSL2) se ven 12 CPU y 15,15 GiB de RAM: la VM de
Docker Desktop ve aproximadamente la mitad de la memoria del equipo. Qué disco aloja el almacenamiento de Docker
no se comprobó.

## C3 · Latencia del feed `all_day` (muestra de 8 peticiones)

```powershell
1..8 | ForEach-Object {
  curl.exe -s -o NUL -w "%{http_code} total=%{time_total}s conexion=%{time_connect}s ttfb=%{time_starttransfer}s bytes=%{size_download}`n" `
    -H "User-Agent: seismic-observatory/1.0" https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson
  Start-Sleep 2
}
```

Resultado: ocho respuestas HTTP 200 de 146.641 bytes. Tiempo total: mediana 102,9 ms, mínimo 84,3 ms, máximo
116,2 ms. Hasta el primer byte: mediana 70,7 ms (de 59,8 a 79,5 ms). Es una muestra pequeña, desde un solo punto de
red y sin repetir en otras horas: indica el orden de magnitud, no una distribución. `ingesta.consultas` no guarda
la latencia.

## C4 · Contraste de cinco eventos con el catálogo FDSN

```powershell
# Para cada id: leer de PostgreSQL (updated, magnitud, longitud, latitud, profundidad) y pedir a FDSN
curl.exe -s "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=<id>&format=geojson"
```

Ids: `ci41570848`, `nc75461397` (con revisiones), `us7000twx1`, `us7000twxf`, `us7000twxn` (los más recientes con
magnitud ≥ 4 de ese momento). Resultado: en los cinco coinciden `updated` (ms), magnitud, longitud, latitud y
profundidad con lo guardado en `live.evento_actual`. Es un contraste de cinco, no una validación del conjunto.

## C5 · Cuántos terremotos faltan en el hueco (recuento FDSN) y qué tipos trae USGS

```powershell
$b = "https://earthquake.usgs.gov/fdsnws/event/1/count?format=geojson&eventtype=earthquake"
curl.exe -s "$b&starttime=2026-11-02T17:11:26&endtime=2026-11-07T13:40:45"
curl.exe -s "$b&minmagnitude=4&starttime=2026-11-02T17:11:26&endtime=2026-11-07T13:40:45"
# Tipos de evento en las ventanas móviles (feed all_day y all_week)
(curl.exe -s https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson | ConvertFrom-Json).features |
  Group-Object { $_.properties.type } | ForEach-Object { "{0}={1}" -f $_.Name, $_.Count }
```

Resultado: entre la última consulta antes del hueco (2026-11-02 17:11:26 UTC) y la primera después
(2026-11-07 13:40:45 UTC, límite de 24 h hacia atrás de la primera consulta tras el reinicio) USGS tiene
**1.171** terremotos (todas las magnitudes) y **81** con magnitud ≥ 4; `maxAllowed` es 20.000. En
`live.evento_actual` hay 0 de ellos (`count(*)` por `ocurrencia` en ese tramo, solo reales). La ventana `all_day` de
ese momento traía 204 eventos, todos `earthquake`. La ventana `all_week` (7 días) traía 1.812: 1.759 `earthquake`,
28 `quarry blast`, 20 `explosion` y 5 `ice quake`.

## C6 · Retención de `data/usgs/`

```powershell
$f = Get-ChildItem data\usgs -Filter *.geojson
"ficheros=$($f.Count) bytes=$(($f | Measure-Object Length -Sum).Sum)"
```

Resultado: 28 ficheros, 4.142.219 bytes (147.936 bytes de media) con fechas desde las 13:40:45 UTC. Las copias del
2 de noviembre ya no existen: es la consecuencia esperada de la retención de 48 h (`FEED_RETENTION_HOURS=48`) tras
una parada de casi seis días.

## C7 · Almacenamiento de Docker

```powershell
docker system df -v | Select-String "seismic-observatory|observatorio-backend|apache/kafka|postgres"
docker compose exec -T kafka sh -c 'du -sk --apparent-size /var/lib/kafka/data; du -sk /var/lib/kafka/data'
```

Resultado: imagen `observatorio-backend:local` 363 MB (compartida por producer, consumer y api); volumen
`seismic-observatory_postgres_data` 103,5 MB; `seismic-observatory_kafka_data` 1,198 GB. Dentro del contenedor de
Kafka el tamaño aparente del directorio de datos es 1.170.148 KiB y el ocupado de verdad 3.688 KiB (3,6 MiB): Kafka
preasigna ficheros de índice y de metadatos y Docker informa del tamaño aparente. Mayor directorio real:
`__cluster_metadata-0` (2.160 KiB); `eventos.live` 3 particiones de 196 a 236 KiB; `eventos.replay` 36 a 40 KiB cada
una.

## C8 · Tiempo de desarrollo y orden de las features (historial de Git)

```powershell
git log --reverse --format="%h|%ad|%s" --date=format:"%Y-%m-%d %H:%M %z"
git show --name-only --format= <hash> | Where-Object { $_ -match '^specs/' }
```

Resultado: ver la tabla de la sección de costes y la de transparencia de `MEMORIA.md`. El primer commit propio del
observatorio es `4ad9473` (2026-11-02 12:42 +01:00); el último de 001–006, `987505e` (2026-11-02 17:56 +01:00); la
spec de 007 es `3157be2` (2026-11-08 14:50 +01:00).

## C9 · Pruebas automáticas

```powershell
docker compose build producer
docker compose run --rm --no-deps producer python -m pytest -q
```

Resultado (2026-11-08): `779 passed`; de ellas, 28 son de `tests/unit/test_mediciones.py`.
