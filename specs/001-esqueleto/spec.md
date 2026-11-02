# Feature Specification: Esqueleto de extremo a extremo (walking skeleton)

**Feature Branch**: `001-esqueleto`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Esqueleto de extremo a extremo del observatorio sísmico: los cinco servicios obligatorios en Docker Compose (kafka, postgres, producer, consumer, api) con healthchecks, reintentos, volúmenes persistentes, retención limitada de Kafka, inicialización versionada de la base de datos, contrato de mensaje Kafka v1, prueba de humo con un evento sintético que recorre producer → Kafka → consumer → PostgreSQL → API con confirmación de offset tras el commit e idempotencia básica, carga del catálogo de países al arrancar, API con endpoint de salud y de estado, configuración por variables de entorno, logs clave=valor y documentación única de puertos, listeners y arranque."

> Es un *walking skeleton*: la base real sobre la que construyen las features
> 002 (ingesta USGS), 003 (calidad, integración geográfica y modelo), 004
> (histórico y replay), 005 (API analítica), 006 (panel) y 007 (memoria). No es
> código desechable: lo que se defina aquí (servicios, contrato, esquemas,
> logs, configuración) lo heredan todas ellas.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Levantar la pila completa con un comando (Priority: P1)

El alumno clona el repositorio en un equipo limpio (Windows + PowerShell, con
Docker), crea su `.env` a partir de `.env.example` y ejecuta
`docker compose up --build -d`. Sin más pasos manuales, los cinco servicios
(Kafka, PostgreSQL, productor, consumidor y API) quedan en marcha y declaran
estar sanos, la base de datos queda inicializada y solo se publican en el
equipo los puertos documentados.

**Why this priority**: sin una pila reproducible no existe ninguna otra
feature, y el enunciado exige este arranque como entregable evaluable
(Enunciado §2, §9, §12; Constitución I).

**Independent Test**: desde un clon limpio, ejecutar el comando de arranque y
comprobar con el estado de Compose que los cinco servicios figuran como
«healthy», con la base inicializada y con solo dos puertos publicados.

**Acceptance Scenarios**:

1. **Given** un clon limpio con `.env` creado desde `.env.example` y las
   imágenes disponibles, **When** se ejecuta `docker compose up --build -d`,
   **Then** en como máximo 120 s el estado de Compose muestra los cinco
   servicios (`kafka`, `postgres`, `producer`, `consumer`, `api`) como
   «healthy» sin ninguna intervención manual.
2. **Given** la pila recién levantada con un volumen de PostgreSQL vacío,
   **When** se consulta el catálogo de la base de datos, **Then** existen tres
   espacios de datos separados (datos live, datos replay e ingesta/calidad) y
   la estructura mínima de la prueba de humo, creados únicamente por los
   ficheros de inicialización versionados en el repositorio.
3. **Given** la pila levantada, **When** se listan los puertos publicados en el
   equipo anfitrión, **Then** solo aparecen `127.0.0.1:8000` (API) y
   `127.0.0.1:9092` (Kafka, solo inspección); PostgreSQL no figura.
4. **Given** un clon limpio **sin** `.env` (o sin la contraseña de PostgreSQL
   definida), **When** se ejecuta el arranque, **Then** falla con un mensaje
   que nombra la variable que falta, sin arrancar con una contraseña por
   defecto.
5. **Given** los tres servicios Python, **When** se inspeccionan sus imágenes,
   **Then** los tres proceden de la misma imagen reproducible y solo difieren
   en el comando de inicio.

---

### User Story 2 - Prueba de humo de extremo a extremo con un evento sintético (Priority: P1)

El alumno ordena al productor publicar un evento SINTÉTICO. El mensaje, con el
contrato v1, viaja por Kafka; el consumidor lo guarda en PostgreSQL en una
única transacción y solo entonces confirma el offset; la API lo muestra. Si el
mismo mensaje se reenvía, o el consumidor se reinicia, no aparecen duplicados.
El evento sintético está claramente marcado y puede eliminarse sin tocar datos
reales.

**Why this priority**: demuestra que todas las piezas están conectadas y fija
las garantías que el resto del proyecto necesita: publicación tras acuse,
offset tras commit y escritura idempotente (Enunciado §5, §7, §11;
Constitución II, III, VI).

**Independent Test**: publicar el evento sintético, consultar el estado en la
API (recuento sintético = 1), reenviar el mismo mensaje (sigue siendo 1),
reiniciar el consumidor (sigue siendo 1) y ejecutar el procedimiento de
eliminación de sintéticos (vuelve a 0).

**Acceptance Scenarios**:

1. **Given** la pila sana y sin eventos, **When** el alumno ordena publicar el
   evento sintético, **Then** el log del productor registra
   `result=publicado` con el `event_id` y la versión solo después del acuse de
   Kafka, y en como máximo 10 s la API informa de 1 evento sintético y 0
   reales, e identifica el evento como sintético en «último evento
   procesado».
2. **Given** el evento ya persistido, **When** se reenvía exactamente el mismo
   mensaje (misma clave y misma versión) una o varias veces, **Then** el
   recuento de eventos en la API no aumenta, no se crea ninguna fila nueva en
   la base de datos y el log del consumidor registra el resultado «omitido»
   (duplicado) con el mismo `event_id` y versión.
3. **Given** el consumidor detenido, **When** se publica el evento sintético y
   después se arranca el consumidor, **Then** el evento se procesa una única
   vez y la API lo refleja; **y Given** el evento ya persistido, **When** se
   reinicia el consumidor, **Then** no reprocesa con efecto visible: el
   recuento no cambia.
4. **Given** una escritura que falla en PostgreSQL (base no disponible),
   **When** el consumidor recibe un mensaje, **Then** no confirma el offset de
   ese mensaje, reintenta, y cuando la base vuelve el mensaje se persiste
   exactamente una vez.
5. **Given** el evento sintético persistido, **When** se ejecuta el
   procedimiento documentado de eliminación de datos sintéticos, **Then** la
   API informa de 0 sintéticos y cualquier dato no sintético previo permanece
   intacto.
6. **Given** el evento sintético persistido, **When** se consultan los
   recuentos «reales» en la API, **Then** el evento sintético no está
   incluido en ellos.

---

### User Story 3 - Arranque y operación tolerantes a dependencias lentas o caídas (Priority: P2)

Kafka o PostgreSQL pueden tardar en estar listos, o caerse durante el uso. Los
servicios que dependen de ellos esperan y reintentan con espera progresiva, lo
dejan registrado en logs y se recuperan solos; su estado de salud refleja la
situación real.

**Why this priority**: el enunciado afirma explícitamente que «el orden de
arranque por sí solo no garantiza que Kafka o PostgreSQL estén preparados»
(Enunciado §2, §5; Constitución I). Sin esto la pila es frágil, pero la
prueba de humo puede demostrarse antes en un arranque favorable.

**Independent Test**: arrancar la pila con PostgreSQL retrasado (o detenerlo
con la pila en marcha) y observar reintentos, estado de salud y recuperación
sin reiniciar nada manualmente.

**Acceptance Scenarios**:

1. **Given** PostgreSQL detenido, **When** se arrancan el resto de servicios,
   **Then** el consumidor y la API no terminan con error: registran cada
   intento de conexión (con número de intento y espera aplicada, creciente
   hasta un tope) y quedan «unhealthy» o «starting»; y **When** PostgreSQL
   arranca, **Then** en como máximo 60 s todos pasan a «healthy» sin
   intervención.
2. **Given** Kafka detenido, **When** se arrancan productor y consumidor,
   **Then** se comportan igual que en el escenario anterior respecto a Kafka.
3. **Given** la pila sana, **When** se detiene PostgreSQL durante la
   ejecución, **Then** el consumidor y la API pasan a «unhealthy» en como
   máximo 60 s, el estado de la API indica el fallo de conexión a la base, y
   **When** PostgreSQL vuelve, **Then** recuperan «healthy» en como máximo 60
   s sin reiniciar contenedores.
4. **Given** esos reintentos, **When** se revisan los logs, **Then** ninguna
   línea contiene contraseñas ni cadenas de conexión completas.

---

### User Story 4 - Reiniciar la pila sin perder datos (Priority: P2)

El alumno apaga y vuelve a encender la pila (por ejemplo, para cerrar el
portátil) y los datos de PostgreSQL y los mensajes de Kafka siguen ahí. La
retención de Kafka es limitada y configurable, de modo que el disco no crece
indefinidamente.

**Why this priority**: el enunciado exige volúmenes persistentes y retención
limitada (Enunciado §9; Constitución I) y las features siguientes acumulan
estado que no puede perderse al reiniciar.

**Independent Test**: con el evento sintético ya persistido, parar la pila
conservando volúmenes, volver a levantarla y comprobar el recuento en la API
y la presencia del mensaje en el topic.

**Acceptance Scenarios**:

1. **Given** el evento sintético persistido, **When** se ejecuta
   `docker compose down` (sin borrar volúmenes) y después
   `docker compose up -d`, **Then** la API informa del mismo recuento y del
   mismo último evento que antes, y el mensaje sigue leíble en el topic
   mientras no haya vencido la retención.
2. **Given** la pila levantada, **When** se consulta la configuración efectiva
   de retención del topic, **Then** coincide con el valor configurado por
   variable de entorno y es finito.
3. **Given** el valor de retención cambiado en `.env`, **When** se recrean los
   servicios afectados, **Then** la retención efectiva refleja el nuevo valor
   sin editar `compose.yaml`.
4. **Given** la documentación, **When** se busca cómo borrar todos los datos,
   **Then** está indicado que `docker compose down -v` los elimina y que es
   la única orden que lo hace.

---

### User Story 5 - Catálogo de países cargado al arrancar (Priority: P2)

Al arrancar, el consumidor lee el catálogo de países montado en solo lectura y
registra cuántos países ha cargado. Si el catálogo falta o es inválido, lo
dice con claridad y no finge que todo va bien.

**Why this priority**: la integración geográfica (feature 003) depende de este
catálogo; detectar pronto un catálogo ausente o corrupto evita fallos
silenciosos después (Enunciado §4.3; Constitución V). Aquí solo se carga y
valida; no se asigna país a ningún evento.

**Independent Test**: arrancar el consumidor con el catálogo entregado y leer
el log; repetir con el fichero ausente y con uno corrupto.

**Acceptance Scenarios**:

1. **Given** el catálogo entregado en el repositorio, **When** arranca el
   consumidor, **Then** su log registra la carga con el número de países
   (242) y el fichero de origen, en los primeros 30 s de funcionamiento.
2. **Given** el catálogo ausente, **When** arranca el consumidor, **Then** el
   log registra un error con el motivo «catálogo ausente» y la ruta esperada,
   el consumidor no procesa mensajes y su estado de salud es «unhealthy».
3. **Given** un catálogo ilegible, vacío, sin geometrías `Polygon`/`MultiPolygon`
   o con `ADM0_A3` ausente o repetido, **When** arranca el consumidor,
   **Then** ocurre lo mismo que en el escenario anterior con un motivo que
   distingue la causa.
4. **Given** el contenedor del consumidor en marcha, **When** se intenta
   escribir en la ruta del catálogo desde el contenedor, **Then** la
   operación es rechazada (solo lectura).

---

### User Story 6 - Diagnosticar y operar con logs, configuración y documentación únicas (Priority: P3)

El alumno (o quien evalúe el proyecto) puede entender el estado de la pila
leyendo logs homogéneos, configurar todo por variables de entorno y encontrar
en un solo sitio los puertos, los listeners de Kafka y los pasos de arranque.

**Why this priority**: es lo que hace la pila defendible y reproducible por
terceros, pero ninguna otra historia depende de ello para funcionar
(Enunciado §5, §9, §12; Constitución VII y Restricciones de plataforma).

**Independent Test**: lanzar la prueba de humo y revisar los logs de los
tres servicios Python; seguir la documentación sin ayuda para reproducir el
arranque y la prueba de humo.

**Acceptance Scenarios**:

1. **Given** la prueba de humo ejecutada, **When** se leen los logs de
   productor, consumidor y API, **Then** cada línea tiene formato
   `clave=valor` e incluye al menos `service` y `result`; las líneas sobre un
   evento incluyen además `event_id` y `updated` (versión).
2. **Given** el repositorio, **When** se examina `.env.example`, **Then**
   enumera todas las variables de configuración con valores de ejemplo o
   vacíos para secretos, sin ninguna credencial real, y `.env` figura como
   ignorado por Git.
3. **Given** la documentación del repositorio, **When** una persona que no
   escribió la pila la sigue desde cero, **Then** consigue levantar la pila,
   ejecutar la prueba de humo y eliminar el evento sintético sin consultar
   otra fuente.
4. **Given** esa documentación, **When** se busca la lista de puertos
   publicados, los listeners de Kafka (interno `kafka:19092`, host
   `localhost:9092`) y el uso previsto de cada uno, **Then** todo está en un
   único apartado.

---

### Edge Cases

- **Dependencias tardías o caídas** (Enunciado §2, §5): cubiertas por la
  historia 3. Los reintentos tienen tope de espera para no saturar ni quedarse
  dormidos indefinidamente.
- **Reenvío tras fallo parcial** (Enunciado §5, §7): si el consumidor guarda
  en PostgreSQL pero cae antes de confirmar el offset, el mensaje se reentrega
  y no debe duplicar el efecto (cubierto por la historia 2, escenarios 2 y 3).
- **Productor sin acuse** (Enunciado §5): si Kafka no confirma la
  publicación, no se registra como publicado y se registra el error.
- **Mensaje que no cumple el contrato**: JSON ilegible, campo obligatorio
  ausente, `schema_version` no soportada, `mode` distinto de `live`/`replay`,
  `mode` que no corresponde al topic, o clave de Kafka distinta del `id` del
  evento original. No se persiste como evento y no puede bloquear la
  partición: va a la cuarentena persistente con motivo, posición (topic,
  partición, offset) y el original (FR-012). Las reglas de validación del
  contenido del evento USGS (coordenadas, tipo, magnitud...) son de la
  feature 003, que amplía esta misma cuarentena.
- **Idempotencia de la cuarentena** (FR-012): es **por posición Kafka**
  (`topic`, partición, `offset`). La reentrega del mismo registro (p. ej. el
  consumidor cae antes de confirmar el offset) no duplica la entrada; en cambio,
  el mismo contenido inválido **publicado de nuevo** recibe otro offset, es un
  mensaje distinto y genera otra entrada.
- **Catálogo ausente o inválido**: historia 5.
- **`.env` ausente o variable obligatoria sin definir**: el arranque falla con
  el nombre de la variable; no se usan secretos por defecto.
- **Puerto del anfitrión ocupado** (8000 o 9092): el arranque falla con el
  error de Docker; la documentación incluye cómo identificar el conflicto.
- **Eliminar y volver a enviar el evento sintético**: tras eliminarlo, volver
  a publicarlo lo crea de nuevo (la idempotencia evita duplicados, no impide
  recrear lo borrado).
- **Retención vencida**: pasada la retención, los mensajes antiguos ya no se
  pueden releer de Kafka, pero lo ya persistido en PostgreSQL permanece.
- **Base de datos con volumen ya existente**: la inicialización versionada se
  aplica al crear un volumen vacío; cómo evolucionar el esquema en volúmenes
  existentes lo decide el plan de esta feature o de la 003 (se documentará en
  `research.md`).
- **Interacción con datos reales futuros**: los recuentos reales y sintéticos
  se informan por separado desde el primer día; un evento sintético nunca
  puede contarse como real (Constitución VI).
- **Casos de dominio USGS diferidos**: revisiones y versiones antiguas,
  envejecimiento fuera del feed, magnitud nula o negativa, profundidad
  negativa, eventos marítimos, puntos en frontera, duplicados entre intervalos
  del histórico y retrasos de publicación no se tratan aquí; son de las
  features 002, 003 y 004.

## Requirements *(mandatory)*

### Functional Requirements

**Despliegue y arranque**

- **FR-001**: La entrega MUST definir en `compose.yaml` cinco servicios
  separados: `kafka`, `postgres`, `producer`, `consumer` y `api`.
  *(Enunciado §2, §9, §12; Constitución I)*
- **FR-002**: La pila MUST arrancar con `docker compose up --build -d` desde un
  clon limpio; el único paso previo permitido es crear `.env` a partir de
  `.env.example`. *(Enunciado §2, §9; Constitución I)*
- **FR-003**: Los tres servicios Python MUST construirse a partir de una única
  imagen reproducible con dependencias fijadas y diferenciarse solo en el
  comando de inicio. *(Enunciado §2, §9; Constitución I)*
- **FR-004**: Cada uno de los cinco servicios MUST declarar un healthcheck. Un
  servicio MUST declararse sano solo cuando tiene establecidas las conexiones
  que necesita para operar, y MUST dejar de estarlo si pierde una de ellas
  hasta recuperarla. *(Enunciado §2, §9; Constitución I)*
- **FR-005**: Productor, consumidor y API MUST reintentar la conexión con cada
  dependencia que usan (Kafka para productor y consumidor; PostgreSQL para
  consumidor y API) con espera progresiva y con tope, tanto al arrancar como
  tras una pérdida de conexión, sin depender del orden de arranque y sin
  terminar con error por no encontrarla. Cada intento MUST quedar en el log
  con su número y la espera aplicada. *(Enunciado §2, §5; Constitución I)*
- **FR-006**: Toda dirección entre servicios dentro de Compose MUST usar
  nombres de servicio; MUST NOT usarse `localhost`. *(Enunciado §9;
  Constitución I)*

**Persistencia y datos**

- **FR-007**: Los datos de PostgreSQL y de Kafka MUST residir en volúmenes
  persistentes; detener y volver a levantar la pila sin borrar volúmenes MUST
  conservar los datos. *(Enunciado §9; Constitución I)*
- **FR-008**: La retención de Kafka MUST ser finita y configurable por variable
  de entorno, con un valor por defecto documentado, y MUST aplicarse al topic
  de eventos sin pasos manuales: el topic existe, con esa retención, antes de
  la primera publicación. *(Enunciado §9; Constitución I)*
- **FR-009**: La inicialización de PostgreSQL MUST estar versionada en el
  repositorio y aplicarse automáticamente al crear un volumen vacío. MUST
  crear espacios de datos separados para datos live, datos replay e
  ingesta/calidad, además de la estructura mínima necesaria para la prueba de
  humo. El modelo completo de eventos queda fuera de esta feature.
  *(Enunciado §7, §9; Constitución VI y Restricciones de plataforma)*

**Contrato de mensaje**

- **FR-010**: El contrato de mensaje Kafka v1 MUST definir: clave = `id` del
  evento original; `schema_version` (valor `1`); `source`; `ingested_at` en
  UTC; `mode` ∈ {`live`, `replay`}; y el evento original sin alterar.
  *(Enunciado §5; Constitución II)*
- **FR-011**: El contrato MUST estar documentado dentro de `specs/`,
  compartido por productor y consumidor (y reutilizable por el replay), y un
  cambio incompatible MUST incrementar `schema_version`. *(Constitución II)*
- **FR-012**: El consumidor MUST tratar un mensaje que incumple el contrato (ver
  casos límite) sin persistirlo como evento y sin bloquear el consumo: MUST
  guardarlo en una cuarentena persistente, en el espacio de ingesta/calidad,
  con motivo, posición (topic, partición, offset), instante de recepción y el
  mensaje original tal como llegó, en la misma transacción que precede a la
  confirmación del offset; y MUST registrarlo en el log con `result=rechazado`.
  Reenviar el mismo mensaje rechazado MUST NOT duplicar la entrada de
  cuarentena. *(Enunciado §6, §7; Constitución IV, II)*

**Prueba de humo e idempotencia**

- **FR-013**: El productor MUST poder publicar, bajo demanda mediante una
  orden documentada, un evento sintético conforme al contrato v1, marcado
  como sintético tanto en el mensaje como en su contenido visible, y con un
  `id` que no pueda confundirse con el de un evento USGS. *(Enunciado §6, §11;
  Constitución VI)*
- **FR-014**: El productor MUST registrar una publicación como realizada solo
  tras el acuse de Kafka; si no hay acuse MUST registrar el error y MUST NOT
  considerarla publicada. *(Enunciado §5; Constitución III)*
- **FR-015**: El consumidor MUST guardar cada mensaje válido en una única
  transacción de PostgreSQL y MUST confirmar el offset solo después de que la
  transacción se haya confirmado. *(Enunciado §7; Constitución III)*
- **FR-016**: Una versión de evento, identificada por (`id`, `updated`), MUST
  existir como máximo una vez en la base; reenviar el mismo mensaje MUST NOT
  crear filas ni aumentar ningún recuento. *(Enunciado §7, §11 «Reenviar la
  misma versión»; Constitución III)*
- **FR-017**: Tras reiniciar el consumidor, MUST reanudar desde el último
  offset confirmado sin duplicar efectos ya persistidos y sin perder mensajes
  publicados mientras estaba parado. *(Enunciado §11 «Reiniciar consumidor»;
  Constitución III)*
- **FR-018**: Por cada versión persistida MUST conservarse: identificador del
  evento, versión (`updated`) en UTC, origen (`source`), modo, marca de
  sintético, instante de ingesta e instante de procesamiento (UTC y
  separados entre sí) y el mensaje original. *(Enunciado §6, §7;
  Constitución IV)*
- **FR-019**: Los datos sintéticos MUST estar identificados de forma que (a)
  queden excluidos por defecto de cualquier recuento «real», y (b) exista un
  procedimiento documentado y repetible que elimine solo los sintéticos sin
  afectar a otros datos. *(Enunciado §6, §10; Constitución VI)*

**Catálogo geográfico**

- **FR-020**: El consumidor MUST recibir `catalogo/paises.geojson` montado en
  solo lectura, cargarlo al arrancar y registrar en el log el número de países
  cargados. *(Enunciado §4.3; Constitución V)*
- **FR-021**: El consumidor MUST validar el catálogo al cargarlo (legible,
  conjunto de entidades no vacío, geometrías `Polygon` o `MultiPolygon`,
  `ADM0_A3` presente y único). Si falta o es inválido MUST registrar un error
  con el motivo concreto, MUST NOT procesar mensajes y MUST declararse no
  sano. *(Enunciado §4.3; Constitución V)*

**API y exposición**

- **FR-022**: La API MUST atender HTTP en `0.0.0.0:8000` dentro del contenedor y
  publicarse en el anfitrión únicamente en `127.0.0.1:8000`. *(Enunciado §9;
  Constitución VII)*
- **FR-023**: La API MUST ofrecer un endpoint de salud, que responde
  satisfactoriamente solo si la API puede operar (incluida la conexión a la
  base de datos), y un endpoint de estado que informe de: conexión a la base
  de datos (correcta/fallida), número de eventos reales, número de eventos
  sintéticos y último evento procesado (identificador, versión, origen y si
  es sintético). Si la base no responde, el estado MUST indicar la conexión
  fallida y MUST NOT sustituir los recuentos por 0 (los informa como no
  disponibles).
  *(Enunciado §2, §8 «Estado del sistema», §11 «Recibir un evento nuevo»;
  Constitución VII)*
- **FR-024**: Ningún endpoint MUST devolver secretos, cadenas de conexión ni
  detalles internos de infraestructura, y la API MUST NOT ofrecer rutas de
  administración. *(Enunciado §9; Constitución VII)*
- **FR-025**: Los únicos puertos publicados en el anfitrión MUST ser
  `127.0.0.1:8000` (API) y `127.0.0.1:9092` (Kafka, solo inspección);
  PostgreSQL MUST NOT publicarse. Kafka MUST exponer dos listeners
  diferenciados (interno `kafka:19092`, host `localhost:9092`).
  *(Enunciado §9; Constitución VII y Restricciones de plataforma)*

**Configuración, logs y documentación**

- **FR-026**: Toda la configuración (dirección de Kafka, topic, credenciales y
  datos de conexión de PostgreSQL, retención de Kafka, parámetros de
  reintento, rutas del catálogo) MUST proporcionarse por variables de entorno;
  `.env.example` MUST enumerarlas sin credenciales reales y `.env` MUST estar
  ignorado por Git. Si falta una variable obligatoria el servicio MUST fallar
  nombrándola. *(Enunciado §5, §9; Constitución VII)*
- **FR-027**: Los logs de los tres servicios Python MUST usar formato
  `clave=valor` e incluir al menos `service` y `result`; las líneas sobre un
  evento MUST incluir `event_id` y `updated`. El resultado MUST pertenecer a
  un conjunto cerrado documentado que cubra como mínimo: publicado,
  persistido, omitido (duplicado), rechazado y error. MUST NOT registrarse
  secretos. *(Enunciado §5; Constitución VII y Restricciones de plataforma)*
- **FR-028**: La documentación MUST reunir en un único apartado: puertos
  publicados y su finalidad, listeners de Kafka, pasos de arranque y parada,
  cómo reiniciar sin perder datos y cómo borrarlos, la retención por defecto,
  la prueba de humo y la eliminación de datos sintéticos. *(Enunciado §9,
  §12; Constitución Restricciones de plataforma)*

### Key Entities

- **Mensaje Kafka v1**: unidad de transporte entre productor y consumidor.
  Atributos: clave (= `id` del evento), `schema_version`, `source`,
  `ingested_at`, `mode` y evento original. Es el contrato compartido que
  heredan la ingesta real y el replay.
- **Evento sintético**: evento ficticio generado a propósito para la prueba de
  humo; estructuralmente válido, identificable a simple vista y por datos,
  excluido del análisis real y eliminable.
- **Versión de evento recibida**: registro persistido de una versión
  (`id`, `updated`) de un evento. Guarda procedencia, modo, marca de
  sintético, instantes de ingesta y procesamiento y el mensaje original. Es
  la semilla del historial y del estado actual de la feature 003.
- **Catálogo de países**: conjunto de entidades geográficas (polígonos y
  atributos, entre ellos `ADM0_A3`) entregado en el repositorio; aquí solo se
  carga y valida.
- **Estado del sistema**: resumen que expone la API: conexión a base de datos,
  recuentos de eventos reales y sintéticos y último evento procesado.
- **Configuración del entorno**: conjunto de variables, con su ejemplo sin
  credenciales, que gobierna servicios, conexiones, topic y retención.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Desde un clon limpio con `.env` creado, los cinco servicios
  figuran como «healthy» como máximo 120 s después de ejecutar el comando de
  arranque (con las imágenes ya descargadas), sin ningún paso manual adicional,
  en 3 arranques consecutivos desde cero.
- **SC-002**: El evento sintético publicado es visible en el estado de la API
  como máximo 10 s después de su publicación, en 3 ejecuciones consecutivas.
- **SC-003**: Reenviar el mismo mensaje 5 veces deja el recuento de eventos
  sintéticos en exactamente 1 y el de reales sin cambios (0 duplicados).
- **SC-004**: Con el consumidor reiniciado en medio de la prueba, el número de
  efectos persistidos por mensaje publicado es exactamente 1 (0 pérdidas, 0
  duplicados).
- **SC-005**: Tras `docker compose down` y `docker compose up -d` sin borrar
  volúmenes, el recuento y el último evento que informa la API son idénticos a
  los previos.
- **SC-006**: Con PostgreSQL (o Kafka) no disponible durante 60 s al arrancar,
  los servicios dependientes alcanzan «healthy» como máximo 60 s después de
  que la dependencia esté disponible, sin intervención manual y sin que
  ningún contenedor se reinicie por error de conexión.
- **SC-007**: Exactamente 2 puertos están publicados en el anfitrión, ambos
  ligados a `127.0.0.1`, y 0 de ellos corresponden a PostgreSQL.
- **SC-008**: Con el catálogo entregado, el log del consumidor informa de 242
  países cargados; con el catálogo ausente o inválido, informa de un error con
  motivo en los primeros 30 s y el consumidor no procesa ningún mensaje.
- **SC-009**: El 100 % de las líneas de log de los tres servicios Python
  siguen el formato `clave=valor` con `service` y `result`, y 0 líneas
  contienen contraseñas o cadenas de conexión completas, tras la ejecución de
  la prueba de humo.
- **SC-010**: Tras ejecutar el procedimiento de eliminación de sintéticos, el
  recuento de sintéticos es 0 y el de reales no varía; en ningún momento un
  evento sintético ha aparecido en un recuento «real».
- **SC-011**: Una persona que no escribió la pila reproduce el arranque, la
  prueba de humo y la eliminación de sintéticos siguiendo solo la
  documentación, en como máximo 15 minutos (sin contar descargas de imágenes).

## Assumptions

- **Alcance geográfico y de fuentes**: esta feature no consulta USGS; el único
  evento que circula es el sintético. La frecuencia de consulta (60 s) es una
  variable de la feature 002 y no se define aquí. *(Enunciado §5)*
- **Un único topic de eventos live**: el skeleton usa un topic para el modo
  `live`, de nombre configurable. El topic y los esquemas de replay se
  definen en la feature 004; aquí solo se reservan los espacios de datos. Un
  mensaje con `mode=replay` recibido en el topic live se rechaza (aislamiento,
  Constitución VI).
- **Marca de sintético**: el contrato v1 identifica el origen sintético en el
  campo `source` (con un valor distinto del de USGS) y el `id` sintético lleva
  un prefijo inconfundible; el contenido visible del evento (p. ej. el texto
  del lugar) lo etiqueta como «SINTÉTICO». El plan fija los valores exactos.
- **Disparo de la prueba de humo**: se hace por una orden explícita y
  documentada, no automáticamente en cada arranque, para que reiniciar la pila
  no contamine la base con eventos sintéticos repetidos. El mecanismo concreto
  lo decide el plan. En reposo, el productor permanece activo y sano
  esperando a la feature 002.
- **Versiones del mismo evento**: en esta feature, una versión es
  (`id`, `updated`) y se guarda como mucho una vez; un mensaje con el mismo
  `id` y otro `updated` se guarda como otra versión, sin decidir cuál es la
  actual. Que el estado actual solo
  cambie con un `updated` más reciente y que una versión antigua no pise a una
  posterior (Enunciado §11, pruebas «Recibir una versión posterior» y «Recibir
  después una versión antigua») son de la feature 003.
- **Cuarentena mínima desde el esqueleto** (decisión del alumno): los mensajes
  que incumplen el contrato se guardan ya en una cuarentena persistente
  (FR-012) en vez de solo en el log, para no incumplir el principio IV de la
  constitución hasta la feature 003. La 003 añade las reglas de validación del
  contenido y amplía esa misma estructura; no la sustituye.
- **Evolución del esquema en un volumen existente**: SQL idempotente en
  `db/init/` más una guarda de versión de esquema al conectar (decisión del plan,
  `research.md` R-07); no se usa herramienta de migraciones.
- **Catálogo defectuoso**: el consumidor no reintenta la lectura (es un
  fichero local); permanece en ejecución pero «unhealthy», sin consumir, hasta
  que se corrige el catálogo y se reinicia el servicio. No se verifica la
  huella contra el manifiesto en esta feature.
- **Valores por defecto de reintento**: espera inicial de 1 s, duplicándose
  hasta un tope de 30 s; configurables. Retención de Kafka por defecto: 7
  días. Ambos valores se documentan y pueden ajustarse por variable de
  entorno.
- **Credenciales**: el alumno crea `.env` desde `.env.example` y define la
  contraseña de PostgreSQL; sin ella, el arranque falla en vez de usar un
  valor por defecto débil.
- **Estado de `compose.yaml` de partida**: solo contiene Kafka y sin volumen
  persistente; esta feature lo amplía a los cinco servicios y añade la
  persistencia.
- **Documentación única**: el apartado único de puertos, listeners y arranque
  vive en el `README.md` del repositorio salvo que el plan justifique otro
  lugar.
- **Entorno de ejecución**: Windows con PowerShell, Docker con Compose v2 y
  acceso a internet para descargar imágenes en el primer arranque.
- **Salud y estado de la API son públicos** (decisión del alumno): el panel
  necesita el «Estado del sistema» (Enunciado §8), así que la salud y el estado
  de la API se pueden consultar a través del túnel. Devuelven solo información
  agregada y sin detalles internos (FR-024). Lo que no se expone son los
  puertos de salud internos de productor y consumidor, que no se publican en
  el anfitrión (Constitución VII, v2.0.1).

## Out of Scope *(fuera de alcance)*

- Consulta real de USGS, `all_day.geojson`, estado de versiones publicadas,
  reintentos HTTP y retención de originales: feature 002.
- Reglas de validación del contenido del evento USGS y la ampliación de la
  cuarentena (la cuarentena mínima por incumplimiento del contrato **sí** es de
  esta feature, FR-012), punto en polígono, país por evento,
  «Sin país asignado», modelo conceptual/lógico/físico de eventos, estado
  actual frente a historial: feature 003.
- Histórico 2025, replay, topic y esquema de replay, etiqueta «REPRODUCCIÓN»:
  feature 004.
- Endpoints analíticos, agregaciones, comparación histórica y CORS para
  Netlify: feature 005.
- Panel Angular + Leaflet, ngrok y Netlify: feature 006.
- Memoria, informe de complejidad, costes y análisis de calidad: feature 007.
- Autenticación, HTTPS en la API, alta disponibilidad, varios nodos de Kafka,
  migraciones de esquema sobre volúmenes existentes (se decide en el plan).

## Trazabilidad

| Historia | Requisitos | Éxito | Pruebas del enunciado §11 cubiertas |
| --- | --- | --- | --- |
| 1 Arranque con un comando | FR-001–004, 006, 009, 022, 025, 026 | SC-001, SC-007 | — (soporte de todas) |
| 2 Prueba de humo | FR-010–019, 023 | SC-002–004, SC-010 | «Recibir un evento nuevo» (con evento sintético), «Reenviar la misma versión», «Reiniciar consumidor» |
| 3 Dependencias | FR-004, 005 | SC-006 | — |
| 4 Persistencia | FR-007, 008 | SC-005 | — |
| 5 Catálogo | FR-020, 021 | SC-008 | — |
| 6 Logs y documentación | FR-024, 026–028 | SC-009, SC-011 | — |
