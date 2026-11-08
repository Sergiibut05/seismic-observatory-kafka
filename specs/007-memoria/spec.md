# Feature 007: Memoria, pruebas de aceptación y defensa

**Rama**: `007-memoria` | **Depende de**: 001–006 (pila completa, API 0.2.0 y panel en local).
Esta feature sube el contrato de la API a 0.3.0 (`modo`, FR-019) y enmienda 005 y 006.

Cierra el proyecto con lo que piden §10, §11, §12 y §13 y aún no existe: la memoria con calidad,
modelo, análisis, complejidad y costes; la evidencia de las once pruebas de aceptación; la
verificación del panel en navegador real; y el procedimiento de defensa. Es sobre todo
documentación; el código nuevo es el mínimo que hace falta para obtener evidencia real
(FR-011, FR-012 y FR-015). Todo número sale de una consulta o un comando reproducible, con fecha.
Nada se inventa ni se redondea a mano.

## Requisitos

- **FR-001** (Enunciado §12): `docs/MEMORIA.md` es el único punto de entrada: índice, flujo
  completo (productor → Kafka → consumidor → PostgreSQL → API → panel) con el fichero, la tabla
  o el log de cada paso, y enlaces a las evidencias. Si se parte en varios ficheros, todos
  cuelgan de ese índice. Cada cifra lleva la consulta o el comando y la fecha de medición.
- **FR-002** (Enunciado §12, §4.1, §6): diccionario de datos: por cada tabla de `live`, `replay`,
  `ingesta` e `historico`, columna, tipo, unidad, nulabilidad y origen (campo USGS, catálogo o
  derivado). Incluye los campos USGS de §4.1 (tipo, unidad, opcionales, frecuencia, errores y
  latencia). `ingesta.consultas` no guarda latencia: se mide aparte con una muestra y se
  declara como tal.
- **FR-003** (Enunciado §12, §4.2, §5): registro de consultas y procedencia: resumen de
  `ingesta.consultas` (consultas, HTTP, errores, copias nuevas, bytes), manifiesto de
  `data/historico/2025/manifest.json` (12 consultas, fecha de extracción, 18.302 eventos,
  duplicados de extremo), huella del catálogo (`catalogo/paises.manifest.json`), retención de
  `data/usgs/` y cómo regenerar cada dato fuera de Git. Documenta el hueco real del 2 al 8 de
  noviembre de 2026 (SQL de huecos) y explica cómo se recuperaría con el catálogo FDSN (§4, §5):
  el procedimiento de `observatorio.historico` (consulta por intervalos, partición si se
  alcanza el tope, deduplicado de extremos, manifiesto) y la carga por el productor; no se
  recupera en esta feature.
- **FR-004** (Enunciado §7, §12): modelo conceptual, lógico y físico. Conceptual y lógico con
  diagrama; físico con el SQL literal de `db/init/`. Para cada tabla: grano, clave, relaciones
  e idempotencia (PK `(event_id, updated)`, estado actual por `updated`, `ON CONFLICT`).
  Justifica cada índice con un `EXPLAIN (ANALYZE, BUFFERS)` real, y explica por qué no hay
  tabla de dimensión de fecha si no la hay (la fecha se deriva de `ocurrencia`).
- **FR-005** (Enunciado §6, §12, §13): apartado de calidad con las seis dimensiones
  (completitud, unicidad, validez, consistencia, actualidad, exactitud). Para cada una: consulta
  SQL reproducible, resultado, antes/después de las reglas (antes = `original` o fichero
  crudo; después = estado actual), 1–3 registros de ejemplo, acción tomada y limitación. Una
  tabla de transformaciones con su número de registros afectados. Solo datos reales;
  los dañados a propósito van aparte y marcados.
- **FR-006** (Enunciado §4.3, §6, §8): limitaciones declaradas con cifras: «Sin país asignado»
  (78 % del histórico, porque el catálogo solo tiene tierra; no es un error ni se asigna al
  país más cercano) y la magnitud con tipos distintos (`magType` en `original`; no es
  comparable sin más). También los registros del feed sin `type=earthquake`, con su motivo.
- **FR-007** (Enunciado §8, §12, §13): análisis con al menos tres conclusiones. Cada una
  cita cifras, filtros y periodo, compara muestras equivalentes (misma magnitud mínima, mismo
  filtro geográfico y de tipo; días con cero incluidos) y lleva la captura del panel con
  los filtros usados. Se declara que no es predicción ni evaluación de riesgo, que la
  cobertura y el tipo de magnitud varían y que el último periodo puede estar incompleto.
- **FR-008** (Enunciado §10): informe de complejidad de tres operaciones: búsqueda de
  versiones por id (lista, diccionario, PK de PostgreSQL), integración geográfica (punto en
  polígono sin y con `STRtree`) y agregación por ventanas (Python y `GROUP BY` en SQL). Coste
  medio y peor caso de cada una, con la fuente del dato (código o plan de consulta).
- **FR-009** (Enunciado §10): mediciones de tiempo y memoria con al menos tres tamaños
  de entrada. Equipo (CPU, RAM, disco, SO, versiones), procedimiento, repeticiones y estadístico
  (mediana y máximo). Compara secuencial frente a diccionario y consulta sin/con índice. Lo
  replicado es sintético: se marca, vive en un esquema temporal o en memoria, se borra al
  terminar y nunca entra en el análisis real. Razona con 100 millones de registros a partir
  de lo medido y dice qué es extrapolación.
- **FR-010** (Enunciado §10): costes de hardware, electricidad, almacenamiento, transferencia,
  mantenimiento y tiempo de desarrollo. Los tamaños y bytes salen de medir
  (`pg_total_relation_size`, `docker system df`, `ingesta.consultas.bytes`); la potencia del equipo
  y los precios son supuestos escritos con su valor. El tiempo de desarrollo sale del historial
  de Git. Una cuota gratuita (Netlify, ngrok) no es coste cero. No se inventa beneficio ni ROI:
  solo se estima si se define un beneficio medible, y si no, se dice. Incluye propuesta de
  escalado, limitaciones y mejoras.
- **FR-011** (Enunciado §11, §12): tabla de las once pruebas de aceptación: prueba → cómo se
  provoca → resultado observado → dónde se ve (log, SQL, endpoint, captura). Ninguna queda sin
  evidencia; si una no se puede probar, se dice por qué y no se marca como superada.
- **FR-012** (Enunciado §11, §6; Constitución VI): casos controlados sin tocar datos reales:
  eventos con id `synthetic-…` y `source` `synthetic-…`, publicados por Kafka en `eventos.live`
  con un comando nuevo junto a `smoke` (nuevo, reenvío, versión posterior, versión antigua,
  magnitud nula, coordenadas inválidas, marítimo, profundidad negativa). La API los excluye
  por defecto. Los inválidos van a cuarentena, que no tiene columna `sintetico`: se
  identifican por la clave `synthetic-…`. Duplicado y revisión de replay usan el topic de replay.
  La limpieza (`scripts/borrar_sinteticos.sql`) debe dejar cero filas sintéticas en
  `live.*` y en `ingesta.cuarentena`; si hoy no lo hace, se amplía el script.
- **FR-013** (Enunciado §11, §8; Constitución VI y VIII): el panel tiene un interruptor visible
  «Incluir casos de prueba sintéticos», apagado por defecto y sin persistir al recargar. Con
  él activo muestra un aviso permanente y la marca «SINTÉTICO» en tabla, ficha y mapa. La
  comparación histórica no los usa (la API ya los ignora). Esto modifica el FR-007 de 006
  («nunca envía `incluir_sinteticos=true`»): se enmienda esa spec antes de tocar el código.
- **FR-014** (Enunciado §8, §9, §11; tarea T11 de 006): verificación del panel en navegador real
  contra la pila en Compose, con las capturas `01`–`08` de T11 en
  `specs/006-panel/evidencias/` y `evidencias/red.md` (peticiones, cabeceras, pestaña oculta
  = 0 rondas). Las capturas de filtros de la memoria salen de aquí o de `specs/007-memoria/evidencias/`.
  El `verifier` no cambia código de producción: un fallo vuelve al `developer`.
- **FR-015** (Enunciado §9, §12): procedimiento de defensa en una sección de la memoria:
  `docker compose up --build -d` y esperar `healthy`, `ngrok http 8000`, URL HTTPS en
  `public/config.json` antes de compilar, `CORS_ORIGEN_NETLIFY` y `docker compose up -d api`,
  `curl.exe -i -X OPTIONS` de comprobación, y plan B local si falla el túnel. Avisa de que la URL de
  ngrok gratuita puede cambiar al reiniciar y exige recompilar. La URL del panel queda como
  «PENDIENTE (alumno)» hasta que exista.
- **FR-016** (Enunciado §12): la «explicación individual del flujo completo y de una decisión
  técnica propia» la escribe el alumno, no el agente. La memoria trae una sección con el
  guion y huecos (`[ESCRIBE: …]`) y la lista de decisiones candidatas con su `research.md`, sin
  elegir ni redactar ninguna. El agente no rellena esos huecos.
- **FR-017** (Enunciado §13; Constitución VIII): sección breve y veraz de transparencia del
  proceso. 001, 005 y 006: subagentes `analyst`, `architect`, `developer` y `verifier`. 002, 003 y
  004: specs compactas escritas directamente por el orquestador, sin subagentes ni
  checklist. 007: spec del `analyst` sin script de Spec Kit, `clarify` ni checklist. Incluye lo no
  verificado en vivo (005: AC-1, AC-2, AC-3 y CORS de Netlify) y T11 hasta que se cierre.
  Se escribe tal cual ocurrió y no se maquilla.
- **FR-018** (Enunciado §13): tabla criterio de rúbrica → sección de la memoria que lo evidencia
  (extracción, calidad, modelado, análisis, reflexión).
- **FR-019** (Constitución VI; Enunciado §11): REPRODUCCIÓN en la API. Parámetro opcional `modo`
  (`live` por defecto | `replay`) en `/eventos`, `/eventos/mapa`, `/recuentos/*` y
  `/distribuciones/*`; en replay lee `replay.evento_actual` (no hace falta la tabla de versiones:
  las agregaciones salen del estado actual). Toda respuesta indica `modo`. En replay cada evento
  lleva `ocurrencia` (tiempo original) y `reproducido_en` (= `ingested_at` del mensaje de replay,
  que `observatorio.replay` fija al publicar; en live es `null`). `/comparacion-historica` es solo
  live: `modo=replay` → 400. `/status` añade `eventos_replay`. Contrato 0.3.0 en
  `docs/CONTRATO-API.md` y `specs/001-esqueleto/contracts/api.openapi.yaml`.
- **FR-020** (Constitución VI; Enunciado §8): REPRODUCCIÓN en el panel. Selector «Datos: En directo /
  REPRODUCCIÓN» (por defecto, en directo, sin persistir al recargar). En replay: franja permanente
  «REPRODUCCIÓN», columna «Reproducido (UTC)» en la tabla, ficha con ambos tiempos, y la
  comparación histórica indica que solo existe en directo (no se pide).

## Decisiones

- **Decisión**: los casos controlados van por `eventos.live` con prefijo `synthetic-`, no por
  replay: solo el estado live llega a API y panel, y la restricción `CHECK` del esquema ya
  impide que un dato real lleve ese prefijo. Replay se usa solo para su propia prueba.
- **Decisión**: sí hay interruptor de sintéticos en el panel. Para la rúbrica, «ND» exige
  verse en el panel y no hay magnitudes nulas reales en live; en la defensa se provoca en
  directo. El riesgo (mezclar sintéticos con el análisis) se cubre con apagado por defecto,
  aviso y marca visible, y haciendo todas las capturas del análisis con el interruptor apagado.
  «Sin país asignado» sí existe en datos reales, así que esa prueba no depende de él.
- **Decisión**: los casos sintéticos llevan `ocurrencia` reciente para verse con los filtros
  por defecto; los de replay conservan la fecha histórica original.
- **Decisión**: «cerrar/abrir el túnel» se prueba en local con `docker compose stop api` y
  `start api`; el túnel real de ngrok lo prueba el alumno en la defensa.
- **Decisión**: «reiniciar consumidor» = `docker compose restart consumer` con un lote
  publicado y se compara el recuento de versiones y de estado actual antes y después.
- **Decisión**: la comparación del análisis usa magnitud ≥ 4 en ambos lados (el feed `all_day`
  trae todas las magnitudes, el histórico solo ≥ 4) y solo ventanas con el sistema encendido.
  El hueco del 2 al 8 de noviembre se excluye o se declara en cada cifra.
- **Decisión**: las mediciones de memoria usan `tracemalloc` (Python) y `EXPLAIN (ANALYZE,
  BUFFERS)` más tamaño de relación (SQL); tamaños mínimos 1.000, 10.000 y 100.000.
- **Decisión** (orquestador, sustituye a la desviación anterior): REPRODUCCIÓN **no** se queda como
  desviación: la Constitución VI la exige en la API y en el panel. Se implementa en esta feature
  (FR-019 y FR-020). Se enmienda la spec de 005 (contrato 0.3.0) y la de 006.
- **Decisión** (orquestador): el hueco del 2 al 8 de noviembre de 2026 **solo se documenta**: la
  memoria explica cómo recuperarlo con el procedimiento FDSN de `observatorio.historico`
  (Enunciado §4 pide «explica cómo recuperar el hueco»). No se recupera.
- **Decisión** (orquestador): el interruptor de sintéticos del panel **sí** existe, apagado por
  defecto y con la marca «SINTÉTICO»; se enmienda la FR-007 de 006.

## Criterios de aceptación

- **AC-1** (§12, entrada única): desde `docs/MEMORIA.md` se llega a cada apartado y evidencia
  con enlaces que no están rotos; no hay cifras sin comando o consulta ni fecha.
- **AC-2** (§12, diccionario): toda columna de las tablas de `live`, `replay`, `ingesta` e
  `historico` aparece con tipo, unidad y origen; una consulta a `information_schema`
  muestra que no sobra ni falta ninguna.
- **AC-3** (§4.2, procedencia): el recuento de `manifest.json` (18.302) coincide con
  `count(*)` de `historico.evento_2025`; el hueco de noviembre sale de una consulta.
- **AC-4** (§6, calidad): las seis dimensiones tienen consulta, resultado, antes/después,
  ejemplo, acción y limitación; las cifras se pueden reproducir copiando la consulta.
- **AC-5** (§8, análisis): hay ≥ 3 conclusiones con cifras, filtros, periodo y captura, y la
  comparación usa magnitud ≥ 4 en ambos lados.
- **AC-6** (§10, complejidad): hay una tabla con las tres operaciones, coste medio y peor
  caso, y ≥ 3 tamaños medidos con tiempo y memoria; los sintéticos están marcados y no
  quedan en el esquema real tras las mediciones (`count` igual que antes).
- **AC-7** (§10, índice): el mismo `EXPLAIN ANALYZE` sin y con índice y la búsqueda secuencial
  frente a diccionario están en la memoria, junto al razonamiento de 100 millones.
- **AC-8** (§11, nuevo y reenvío): el evento `synthetic-…` nuevo da una fila actual visible en API
  y panel (con el interruptor); reenviar la misma versión deja el recuento igual.
- **AC-9** (§11, revisión): una versión posterior cambia magnitud y/o país y mueve los
  recuentos afectados; después una versión antigua no cambia nada. Se ve en SQL y en API.
- **AC-10** (§11, nulo y marítimo): magnitud nula se conserva como `null` y se ve «ND» en
  tabla, ficha y leyenda; el marítimo sale como «Sin país asignado» y sigue en los recuentos.
- **AC-11** (§11, inválidos): coordenadas inválidas dejan una fila en `ingesta.cuarentena` con
  motivo, ninguna en `live.*` y ningún punto en el mapa.
- **AC-12** (§11, consumidor): con `restart consumer` en mitad de un lote no aumenta el número
  de versiones ni de eventos y el lag vuelve a 0.
- **AC-13** (§11, túnel): con `stop api`, en ≤ 60 s el panel muestra el error y marca la última
  lectura; con `start api`, se recupera sin recargar. Hay capturas `07` y `08`.
- **AC-14** (§11, replay): tras `python -m observatorio.replay` hay filas solo en `replay.*`, con
  `mode='replay'` y log `etiqueta=REPRODUCCIÓN`; `eventos_reales` y los recuentos de la API en
  `modo=live` no cambian; el duplicado no crea fila y la revisión sí. Con `modo=replay` la API
  devuelve esas filas con `modo`, `ocurrencia` y `reproducido_en`.
- **AC-19** (Constitución VI, API): `modo` inválido → 400; `/comparacion-historica?modo=replay` →
  400; `/status` trae `eventos_replay`; la suma de `/recuentos/pais?modo=replay` = total de
  `/eventos?modo=replay` = `count(*)` de `replay.evento_actual`.
- **AC-20** (Constitución VI, panel): con el selector en REPRODUCCIÓN hay franja visible, columna de
  tiempo de reproducción y ninguna petición a `/comparacion-historica`; al volver a «En directo»
  desaparece todo. Captura `09-reproduccion`.
- **AC-15** (§11, limpieza): tras `scripts/borrar_sinteticos.sql`, el recuento de reales es el
  de antes y no queda ninguna fila sintética en `live.*` ni en cuarentena.
- **AC-16** (§8, panel): con el interruptor apagado ningún sintético aparece ni sale en
  `incluir_sinteticos=true`; con él encendido hay aviso y marca. Las capturas `01`–`08` existen y
  la suma de recuentos por país coincide con el total de tabla y mapa.
- **AC-17** (§12, alumno): la sección de explicación individual existe con huecos y ninguno
  está relleno por el agente; la URL de Netlify y el authtoken de ngrok no están en Git.
- **AC-18** (§13): la tabla de rúbrica enlaza cada criterio con evidencias existentes.

## Fuera de alcance

Publicar en Netlify, la cuenta y el authtoken de ngrok, la URL pública del panel, la explicación
individual de §12, ROI sin beneficio medible, recuperar el hueco de noviembre (solo se documenta),
reconciliación de eventos eliminados por USGS, automatizar informes de calidad y un panel de
calidad en Angular.

## Hecho cuando

`docs/MEMORIA.md` cubre FR-001 a FR-020, AC-1 a AC-20 tienen evidencia en
`specs/007-memoria/evidencias/` (y las capturas de T11 en `specs/006-panel/evidencias/`), T11 de
006 está cerrada, no quedan sintéticos en la base y solo falta lo que hace el alumno
(Netlify, ngrok y la explicación individual).
