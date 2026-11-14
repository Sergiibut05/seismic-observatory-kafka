# Plan 013: varias fuentes fusionadas con Spark

- **Rama**: `013-multifuente` (local) | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)
- **Stack**: el del backend (Python 3.12, aiokafka 0.15, psycopg 3) + PySpark 4.2.1 con `spark-sql-kafka-0-10_2.13:4.2.1` y Java 17, en una imagen aparte.
- **Contratos**: [contracts/mensajes-kafka.md](./contracts/mensajes-kafka.md) (fuente v1, fusionado v2). API: solo campos nuevos.

## Arquitectura

```text
USGS feed ─► producer      ─► eventos.usgs ┐
EMSC FDSN ─► producer-emsc ─► eventos.emsc ├─► fusion (PySpark) ─► eventos.live ─► consumer ─► PostgreSQL ─► API ─► panel
relleno (puntual) ─────────► los mismos topics ┘        │
                                                        └─ estado en PostgreSQL (esquema fusion)
```

## Decisiones

1. **Productor genérico por fuente** (`producer/fuentes.py`): un adaptador por fuente con su URL, su clasificación (qué es terremoto, versión) y su nombre. `ciclo.una_pasada` recibe el adaptador; el resto (descarga, original, publicadas, consultas, exclusiones, logs) es común. `FUENTE=usgs|emsc` en el entorno elige el adaptador; `TOPIC_FUENTE` (por defecto `eventos.<fuente>`).
2. **EMSC**: FDSN con `start = ahora − 26 h`, `limit=10000`, `format=json`. `evtype == "ke"`; versión = `lastupdate` en ms.
3. **Contrato** (`common/contrato.py`): `validar_mensaje` acepta v1 (como hoy) y v2 (solo `live`); `MensajeValido` gana `fuentes: tuple[str, ...]` (v1: `(source,)`). `construir_mensaje_v2` serializa de forma determinista.
4. **Fusión en Python puro** (`observatorio/fusion/`):
   - `normalizar.py`: mensaje de fuente → `Informe` o `Descarte` (motivo de lista cerrada). Mismas reglas que `consumer/calidad.py`.
   - `emparejar.py`: `fusionar(nuevos, guardados, canonicos) → Resultado` con los informes y eventos a guardar y los mensajes v2 a emitir. Regla FR-004, id FR-005, principal FR-006, versión FR-007. Candidatos indexados por hora (`bisect`).
   - `estado.py` (psycopg síncrono): DDL y siembra (`asegurar_fusion`), carga de informes en `[t_min − 30 s, t_max + 30 s]` y de sus eventos, guardado.
   - `job.py`: `SparkSession` local, `readStream` de Kafka con `subscribePattern = eventos\.(usgs|emsc)`, `startingOffsets=earliest`, `maxOffsetsPerTrigger=5000`, *checkpoint* en volumen, `trigger(processingTime="15 seconds")`. En `foreachBatch`: con Spark SQL saca fuente, id y versión (`get_json_object`) y se queda con la última versión de cada informe del lote (`row_number` por `(topic, key)`); `collect` (≤ 5.000 filas); normaliza y fusiona en Python; escribe los v2 con `df.write.format("kafka")` (`kafka.acks=all`, `kafka.enable.idempotence=true`); `COMMIT` del estado.
   - Salud: un hilo toca `/tmp/fusion-latido` cada 10 s mientras la consulta está activa; el healthcheck comprueba que el fichero tiene menos de 60 s.
5. **Consumidor**: persiste `fuentes` (historial y estado actual). `rellenar_estado` las saca del original (v2) o de `source` (v1). Sin más cambios: la versión del evento fusionado es monótona, así que el upsert por `updated` sigue valiendo.
6. **Relleno** (`observatorio/relleno.py`): `python -m observatorio.relleno --desde 2025-01-01 --hasta ahora --magnitud-min 2.5 --fuentes usgs,emsc`. Plan de intervalos puro (`planificar`) con el recuento de cada fuente: parte por la mitad mientras `count > tope` (USGS 15.000, EMSC 8.000). Descarga, conserva el original en `/data/relleno/<fuente>/`, clasifica con el mismo adaptador, publica en el topic de la fuente con acuse y marca `ingesta.publicadas`. Repetirlo no republica.
7. **API**: `fuentes` en `/eventos` y `/eventos/mapa`; `/status` añade `ingesta_por_fuente` (última consulta correcta de cada fuente). Aditivo.
8. **Panel**: `fuentes` en el modelo; la ficha del mapa y la tabla dicen «USGS», «EMSC» o «EMSC + USGS»; atribución «Datos: USGS · EMSC (CC BY 4.0)»; la cabecera rotula «Ingesta» con el detalle por fuente en el `title`.
9. **Compose**: `producer` (`FUENTE=usgs`), `producer-emsc` (`FUENTE=emsc`), `fusion` (imagen `observatorio-fusion:local`, `backend/Dockerfile.fusion`). Volumen `fusion_checkpoint`. Los cinco servicios del enunciado siguen.

## Constitución (3.0.0)

- **I**: siguen los cinco servicios; se añaden `producer-emsc` y `fusion`, con healthcheck y reintentos (la fusión se reinicia con `restart: unless-stopped` y continúa desde el *checkpoint*).
- **II**: dos contratos documentados en `contracts/`; v2 sube `schema_version`.
- **III**: productores igual que antes por `(fuente, id, updated)`; fusión determinista y Kafka antes del `COMMIT` (research.md, tabla de fallos); el consumidor no cambia su orden.
- **IV**: originales conservados (feed en `/data/<fuente>/`, relleno en `/data/relleno/`; cada informe dentro del v2); descartes de la fusión con motivo; tipo por fuente.
- **V**: el país sigue saliendo del punto del evento fusionado (el de la fuente principal).
- **VI**: replay, humo y sintéticos sin cambios (v1).
- **VII**: nada nuevo expuesto; Spark UI no se publica.
- **VIII**: Spark justificado en research.md; umbrales medidos (evidencias/umbrales-*.txt).

## Estructura

```text
backend/
  Dockerfile.fusion                 # python 3.12 + Java 17 + pyspark 4.2.1 + conector Kafka
  requirements-fusion.txt
  observatorio/
    common/contrato.py              # v1 + v2
    common/config.py                # FUENTE, TOPIC_FUENTE, EMSC_URL_BASE; ajustes de fusión y relleno
    producer/fuentes.py             # adaptadores USGS y EMSC
    producer/ciclo.py | app.py      # genéricos por fuente
    fusion/normalizar.py | emparejar.py | estado.py | job.py | salud.py | __main__.py
    relleno.py                      # relleno 2025–2026
    consumer/persistencia.py        # fuentes
    api/consultas.py | rutas.py | calculos.py | estado.py
  tests/unit/test_fuentes.py | test_normalizar.py | test_emparejar.py | test_contrato_v2.py | test_relleno.py
db/init/006_multifuente.sql
compose.yaml, .env.example
frontend/src/app/modelos/api.ts, componentes/mapa/mapa-ficha.ts, componentes/tabla, componentes/estado
docs/FUENTES-Y-LICENCIAS.md, docs/CONTRATO-API.md, README.md
```

## Pruebas

- **pytest** (sin infraestructura): normalización de las dos fuentes con fixtures reales; emparejamiento (pareja dentro y fuera de umbral, réplicas de la misma fuente, dos candidatos, id estable, principal por región, revisión, reentrega sin emisión, determinismo); contrato v2 y sus motivos; clasificación EMSC; plan de intervalos del relleno.
- **Pila real**: Europa con eventos; SC-002 medido con SQL sobre `live.evento_actual` y `fusion.informe`; parar `fusion` a mitad de lote; relleno completo con recuentos por mes; todo en `evidencias/`.
