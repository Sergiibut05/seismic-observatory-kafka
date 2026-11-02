# Contrato: formato de logs `clave=valor`

**Aplica a**: `producer`, `consumer`, `api` (y a la prueba de humo). **Implementación**: `backend/observatorio/common/logging.py`.
**Requisitos**: FR-027, SC-009, Constitución «Restricciones de plataforma».

## Formato

Una línea por registro, pares `clave=valor` separados por un espacio, escrita en la salida
estándar (la recoge `docker compose logs`):

```text
ts=2026-11-02T12:00:00.123Z level=INFO service=consumer result=persistido event_id=synthetic-smoke-0001 updated=1767225600000 topic=eventos.live partition=2 offset=0
```

| Clave | Siempre | Contenido |
| --- | --- | --- |
| `ts` | sí | UTC, ISO 8601 con milisegundos y `Z` |
| `level` | sí | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `service` | sí | `producer`, `consumer` o `api` |
| `result` | sí | Valor del conjunto cerrado de abajo |
| `event_id`, `updated` | en toda línea **sobre un evento** | `updated` = milisegundos epoch de la versión; `-` si no se pudo determinar (mensaje ilegible) |
| resto | opcional | `topic`, `partition`, `offset`, `motivo`, `attempt`, `wait_s`, `dependency`, `reason`, `component`, `paises`, `fuente`, `action`, `error`, `exc` … |

Reglas de escritura:

- Los valores sin espacios ni `=` ni `"` ni `\` ni saltos de línea van sin comillas.
- En otro caso van entre comillas dobles, escapando `\` y `"`; los saltos de línea se
  escriben como `\n` literal. **Nunca hay una línea partida en dos** (un *traceback* va en
  `exc="…"`).
- Los valores secretos conocidos se sustituyen por `***`. No se registran contraseñas,
  cadenas de conexión ni el contenido de `.env`.
- Los registros de librerías (aiokafka, psycopg, uvicorn) pasan por el mismo formateador;
  si no traen `result`, se añade `result=info` (o `result=error` si el nivel es ≥ ERROR) y el
  texto original va en `msg="…"`.

## Conjunto cerrado de `result`

| `result` | Quién | Significado |
| --- | --- | --- |
| `publicado` | producer | Kafka acusó recibo (`send_and_wait`). Incluye `event_id`, `updated`, `topic`, `partition`, `offset` |
| `persistido` | consumer | Versión nueva guardada y commit de BD hecho (el offset se confirma después) |
| `omitido` | consumer | Versión ya existente (duplicado); no se crea fila. Incluye `reason=duplicado` |
| `rechazado` | consumer | Mensaje a cuarentena. Incluye `motivo`, `topic`, `partition`, `offset` (y `event_id`/`updated` si se conocen) |
| `error` | todos | Fallo (sin acuse de Kafka, error no clasificado, catálogo inválido, esquema desactualizado…). Incluye `reason` |
| `iniciado` | todos | Servicio arrancado o componente en arranque |
| `listo` | todos | Componente listo (`component=catalogo`, `component=kafka`, `component=postgres`, `component=topic`) |
| `reintento` | todos | Intento fallido de conexión; incluye `dependency`, `attempt`, `wait_s`, `reason` |
| `detenido` | todos | Parada ordenada |
| `info` | todos | Otras informaciones (incluidas las de librerías) |

`reason`/`motivo` nunca contienen secretos: solo códigos (`topic_no_existe`,
`conexion_rechazada`, `esquema_desactualizado`, `catalogo_ausente`…) o el nombre de la clase
de excepción.

## Ejemplos

```text
ts=… level=INFO  service=producer result=iniciado
ts=… level=INFO  service=producer result=reintento dependency=kafka attempt=1 wait_s=1 reason=KafkaConnectionError
ts=… level=INFO  service=producer result=listo component=topic action=topic_creado topic=eventos.live partitions=3 retention_ms=604800000
ts=… level=INFO  service=producer result=publicado event_id=synthetic-smoke-0001 updated=1767225600000 topic=eventos.live partition=2 offset=0
ts=… level=INFO  service=consumer result=listo component=catalogo paises=242 fuente=/catalogo/paises.geojson
ts=… level=INFO  service=consumer result=persistido event_id=synthetic-smoke-0001 updated=1767225600000 topic=eventos.live partition=2 offset=0
ts=… level=INFO  service=consumer result=omitido event_id=synthetic-smoke-0001 updated=1767225600000 reason=duplicado topic=eventos.live partition=2 offset=1
ts=… level=WARNING service=consumer result=rechazado event_id=- updated=- motivo=json_ilegible topic=eventos.live partition=0 offset=7
ts=… level=ERROR service=consumer result=error component=catalogo motivo=catalogo_ausente fuente=/catalogo/paises.geojson
ts=… level=INFO  service=api result=info method=GET path=/status status=200 ms=4
```

## Comprobación (SC-009)

Todas las líneas deben cumplir (el prefijo `nombre-1  | ` lo añade Compose):

```text
^(\S+\s+\|\s+)?ts=\S+ level=\S+ service=(producer|consumer|api) result=\S+( .*)?$
```
