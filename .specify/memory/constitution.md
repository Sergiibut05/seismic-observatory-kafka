# Constitución del Observatorio de Actividad Sísmica

## Core Principles

### I. Entorno reproducible en Docker Compose
Productor, Kafka, consumidor, PostgreSQL y API MUST ser cinco servicios
separados de `compose.yaml` que arrancan juntos con
`docker compose up --build -d` desde un clon limpio. Los servicios Python MUST
construirse desde una imagen reproducible con dependencias fijadas; MAY
compartir imagen con comandos de inicio distintos. Cada servicio MUST declarar
healthcheck, y quien dependa de Kafka o PostgreSQL MUST reintentar la conexión
con espera progresiva: el orden de arranque no garantiza disponibilidad. Los
datos MUST vivir en volúmenes persistentes y Kafka MUST tener retención
limitada. Dentro de Compose las direcciones MUST usar nombres de servicio,
nunca `localhost`.

### II. Contrato de mensaje explícito y versionado
Todo mensaje en Kafka MUST usar el `id` del evento USGS como clave y MUST
incluir `schema_version`, `source`, `ingested_at`, `mode` (`live` o `replay`)
y el evento original sin alterar. El contrato MUST estar documentado en
`specs/` y compartido por productor, replay y consumidor; un cambio
incompatible MUST subir `schema_version`. La API MUST documentar su contrato
en `docs/CONTRATO-API.md` y el panel MUST consumir solo campos definidos ahí,
nunca la respuesta cruda de USGS.

### III. Al menos una vez con escritura idempotente (NO NEGOCIABLE)
El productor MUST marcar una versión `(id, updated)` como publicada solo
después del acuse de Kafka. El consumidor MUST escribir cada mensaje en una
única transacción de PostgreSQL y MUST confirmar el offset después del commit.
Restricciones únicas y upsert MUST impedir que un reenvío aumente recuentos.
El estado actual de un evento MUST cambiar solo si la versión recibida tiene un
`updated` más reciente; toda versión recibida MUST quedar en el historial sin
sobrescribir una posterior. El orden por partición MUST NOT sustituir a la
comparación de versiones. Las agregaciones MUST calcularse desde el estado
actual, nunca sumando mensajes.

### IV. Trazabilidad y calidad explícita
El GeoJSON original y los metadatos de cada extracción (consulta, fecha,
número de registros, estado HTTP) MUST conservarse antes de transformar, con
una retención definida que evite copias idénticas indefinidas. Cada regla de
validación y transformación MUST estar escrita, probada y contabilizada
(registros afectados). Un registro que no se puede tratar MUST ir a cuarentena
con motivo y referencia al original; MUST NOT descartarse en silencio ni
inventarse valores. Los nulos MUST NOT rellenarse con cero; magnitudes y
profundidades negativas MUST estudiarse antes de rechazarse. Las fechas MUST
almacenarse en UTC, separando tiempo de ocurrencia, actualización USGS e
ingesta. Solo se publican como terremotos los eventos con
`properties.type == "earthquake"`; el resto MUST conservar su motivo de
exclusión.

### V. Integración geográfica por geometría
El país de un terremoto MUST obtenerse por punto dentro de polígono contra el
catálogo Natural Earth en EPSG:4326; MUST NOT deducirse del texto de `place`.
`ADM0_A3` MUST verificarse como único antes de usarse como clave y MUST NOT
asumirse como código ISO. La regla para puntos en frontera o con varias
coincidencias MUST estar documentada y ser determinista. Un punto sin
coincidencia MUST quedar como «Sin país asignado» y permanecer en el análisis;
MUST NOT tratarse como error ni asignarse al país más cercano.

### VI. Aislamiento de replay y datos sintéticos
La reproducción histórica MUST viajar por Kafka en un topic propio, MUST
escribir en un esquema o tablas separados de los datos live, MUST conservar el
tiempo original y añadir el de reproducción, y MUST etiquetarse «REPRODUCCIÓN»
en API y panel. El replay MUST reutilizar el mismo procesamiento del
consumidor. Datos ficticios, casos dañados a propósito y réplicas para pruebas
de escala MUST estar marcados como sintéticos y MUST NOT entrar en el análisis
real ni en las conclusiones.

### VII. Superficie mínima expuesta y sin secretos
Solo la API de consulta MAY publicarse, y solo a través de ngrok o en
`127.0.0.1`. Kafka, PostgreSQL, rutas de administración y los endpoints de
salud internos de productor y consumidor MUST NOT exponerse por el túnel. La
salud y el estado de la API MAY ser públicos si devuelven solo información
agregada, porque el panel muestra el estado del sistema. CORS MUST autorizar solo el origen exacto de
Netlify y el de desarrollo. El repositorio, la imagen y el bundle de Angular
MUST NOT contener secretos: el authtoken de ngrok y las contraseñas viven en
`.env` (ignorado por Git) y `.env.example` MUST ir sin credenciales. La API
MUST escuchar en `0.0.0.0:8000` en HTTP dentro de Docker; el HTTPS lo aporta
ngrok.

### VIII. Simplicidad y evidencia
La pila MUST limitarse a lo que exige `docs/ENUNCIADO.md`: sin Spark, Flink,
Kubernetes ni aprendizaje automático. Una dependencia, servicio o abstracción
adicional MUST justificarse en el `research.md` de la feature. Cada feature
MUST cerrar con evidencia verificable (tests, consultas, capturas o logs)
ligada a las pruebas de aceptación del apartado 11 del enunciado. Toda
afirmación analítica MUST citar cifras, filtros y periodo, comparar muestras
equivalentes y MUST NOT presentarse como predicción ni evaluación de riesgo.

## Restricciones de plataforma

- Backend en Python 3.12 con `aiokafka`, `asyncpg`/`psycopg`, `shapely` y
  `fastapi`/`uvicorn`; versiones fijadas en `requirements.txt`.
- Kafka 4.1 en modo KRaft, un único nodo, sin ZooKeeper. El listener interno
  es `kafka:19092`; el del host, `localhost:9092`, solo para inspección.
- PostgreSQL con esquema inicial versionado en `db/init/`. Índices y
  restricciones MUST justificarse en el `data-model.md` de la feature.
- Frontend Angular + Leaflet compilado como SPA y publicado en Netlify. La URL
  de la API se lee de `public/config.json`. El panel consulta la API cada 60 s
  y el productor consulta USGS cada 60 s, de forma independiente.
- Datos descargados (histórico, originales) fuera de Git, en `data/`, con un
  script que los regenera. Los puertos publicados al host se documentan en un
  único sitio.
- Los logs de productor y consumidor MUST identificar servicio, `event_id`,
  versión y resultado (publicado, omitido, actualizado, cuarentena, error).

## Flujo de trabajo

- `docs/ENUNCIADO.md` es la fuente de requisitos. Toda spec MUST trazar sus
  requisitos a un apartado del enunciado.
- Desarrollo dirigido por especificación con Spec Kit: `spec.md` →
  `plan.md` → `tasks.md` → implementación → verificación, en una rama
  `NNN-nombre` por feature. Un cambio de comportamiento MUST actualizar spec o
  plan antes que el código.
- Roles: `analyst` redacta y aclara la spec; `architect` produce plan, modelo
  de datos y contratos; `developer` implementa por tareas con tests; `verifier`
  ejecuta `/speckit-analyze`, tests y pruebas de aceptación, y guarda evidencias
  en `specs/NNN-nombre/evidencias/` sin tocar código de producción.
- La lógica de validación, versionado e integración geográfica MUST tener tests
  unitarios con pytest. Antes de fusionar una feature, la pila MUST arrancar con
  Docker Compose y sus pruebas MUST pasar.
- Las decisiones técnicas relevantes MUST registrarse en el `research.md` de la
  feature con alternativas descartadas, para poder defenderlas individualmente.
- Documentación, mensajes de commit y comentarios en español.

## Governance

Esta constitución prevalece sobre atajos locales y convenciones no escritas;
solo `docs/ENUNCIADO.md` está por encima en cuanto a requisitos. Una enmienda
MUST documentarse en este fichero, MUST incrementar la versión según semver e
incluir la fecha. MAJOR elimina o redefine un principio; MINOR añade un
principio o sección o amplía materialmente una regla; PATCH aclara redacción
sin cambiar la regla. El cumplimiento se comprueba en el «Constitution Check»
de cada `plan.md` y en la verificación final de cada feature: arranque con un
comando, contrato versionado, idempotencia probada, cuarentena con motivo,
aislamiento de replay, ausencia de secretos y ausencia de complejidad no
justificada.

**Version**: 2.0.1 | **Ratified**: 2026-10-26 | **Last Amended**: 2026-11-02
