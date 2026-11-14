# Feature Specification: varias fuentes sísmicas fusionadas con Spark

**Feature Branch**: `013-multifuente`

**Created**: 2026-11-14

**Status**: Borrador

**Input**: El panel solo enseña bien América: el feed de USGS trae la sismicidad pequeña de EE. UU. y, del resto del mundo, casi solo M ≥ 4,5. Medido el 2026-11-12, en 24 h: Europa 0 eventos en USGS frente a 98 en EMSC; EE. UU. continental 132 en USGS frente a 19 en EMSC. Se pide añadir EMSC como segunda fuente, un topic por productor, una etapa de PySpark que junte las dos fuentes sin duplicar un mismo terremoto (por la hora en que ocurrió, no por cuándo se procesó) y escriba en un topic que haga el papel del `eventos.live` actual, y rellenar PostgreSQL con todo 2025 y lo que va de 2026.

Ampliación sobre 001–011. Enmienda la constitución a 3.0.0 (principios II y VIII). La copia de `main` previa está en `respaldo/main-antes-multifuente`.

## Cambios respecto a specs anteriores

- **001 / 002 (contrato y productor)**: el productor USGS ya no escribe en `eventos.live`, sino en `eventos.usgs`. La clave de `eventos.live` deja de ser el id USGS: es el id canónico del evento fusionado (contrato v2). El contrato v1 sigue vigente para los topics por fuente y para `eventos.replay`.
- **003 (consumidor)**: lee `eventos.live` con contrato v2 (y sigue aceptando v1 para la prueba de humo, los casos sintéticos y la reproducción). Guarda las fuentes de cada evento.
- **005 (API)**: los eventos devuelven sus fuentes. Ningún endpoint se quita ni cambia de forma incompatible.
- **006 (panel)**: la ficha del evento dice de qué fuentes viene; la atribución incluye EMSC.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver terremotos de Europa (Priority: P1)

Quien abre el panel ve terremotos en Europa y el Mediterráneo, no solo en América, con la misma frescura que hoy (consulta cada 60 s).

**Independent Test**: con la pila en marcha, contar en la API los eventos de las últimas 24 h dentro de la caja de Europa (lat 34–72, lon −25–45).

**Acceptance Scenarios**:

1. **Given** la pila en marcha durante 10 minutos, **When** se piden los eventos de las últimas 24 h en Europa, **Then** hay más de cero y su número es del orden del de EMSC para el mismo periodo.
2. **Given** EMSC caído (sin red o HTTP 5xx), **When** pasa un ciclo, **Then** USGS sigue entrando y el productor EMSC reintenta con espera creciente sin parar el proceso.

---

### User Story 2 - Un terremoto, una fila (Priority: P1)

Un terremoto que publican USGS y EMSC aparece una sola vez en el mapa, en la tabla y en los recuentos, con las dos fuentes indicadas en su ficha.

**Independent Test**: tomar un terremoto M ≥ 4 que esté en las dos fuentes y comprobar que la API devuelve una sola fila con `fuentes = [emsc, usgs]`.

**Acceptance Scenarios**:

1. **Given** informes de USGS y EMSC a ≤ 30 s y ≤ 100 km, **When** pasan por la fusión, **Then** queda un solo evento con las dos fuentes.
2. **Given** dos informes de la misma fuente muy próximos (una réplica), **When** pasan por la fusión, **Then** quedan dos eventos distintos.
3. **Given** un evento ya fusionado, **When** llega una revisión de cualquiera de sus fuentes, **Then** el evento conserva su id y su estado actual pasa a la versión nueva (historial completo).
4. **Given** la fusión se cae a mitad de un lote, **When** vuelve a arrancar, **Then** no se pierde ningún evento ni se duplica ninguna fila.

---

### User Story 3 - Histórico 2025–2026 en la base (Priority: P2)

Un filtro por país o por fechas pasadas devuelve resultados aunque el sistema lleve poco tiempo en marcha: la base tiene todos los terremotos M ≥ 2,5 de 2025 y de 2026 hasta hoy, de las dos fuentes, fusionados.

**Independent Test**: lanzar el relleno, esperar a que termine y comparar los recuentos por mes con los de las fuentes.

**Acceptance Scenarios**:

1. **Given** la base sin histórico, **When** se lanza el relleno de 2025-01-01 a hoy con M ≥ 2,5, **Then** cada informe de cada fuente pasa por la fusión una vez y la base queda con eventos de todos los meses.
2. **Given** un intervalo con más filas de las que la fuente devuelve en una consulta (EMSC corta a unas 10.000 sin avisar; USGS rechaza más de 20.000), **When** se rellena, **Then** el intervalo se parte hasta que cada consulta cabe y no se pierde ninguno.
3. **Given** el relleno interrumpido a mitad, **When** se vuelve a lanzar, **Then** no se republica lo ya publicado y el resultado final es el mismo.

---

### Edge Cases

- EMSC marca un evento como `se` (sospechoso) o `ue` (desconocido): no se publica; queda en exclusiones con motivo.
- Profundidad de EMSC: llega negativa en la geometría y positiva en `properties.depth`; se usa la de `properties`.
- Un informe sin hora, con coordenadas fuera de rango o con magnitud no numérica: la fusión lo descarta con motivo (no se inventa nada).
- Un informe de una fuente encaja con dos eventos candidatos: se elige el de menor distancia combinada (tiempo y espacio).
- Un evento que existía antes de esta feature (id USGS): al llegar su pareja de EMSC conserva el id USGS; no aparece duplicado.
- Revisión de un informe que lo movería fuera de la ventana de su evento: sigue en su evento (la pertenencia no se recalcula; ver research.md).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: un productor por fuente (USGS y EMSC), con la misma imagen y el mismo ciclo (consulta cada 60 s, original conservado, publicado solo tras el acuse, marca `(fuente, id, updated)`), cada uno a su topic (`eventos.usgs`, `eventos.emsc`). Enunciado §2, §4.
- **FR-002**: EMSC se consulta por FDSN (`/fdsnws/event/1/query`, JSON) con una ventana de 26 h; solo `evtype == "ke"`; versión = `lastupdate`.
- **FR-003**: un servicio de fusión con PySpark Structured Streaming lee los topics por fuente y escribe en `eventos.live` con el contrato v2.
- **FR-004**: regla de fusión: dos informes son el mismo terremoto si son de fuentes distintas, sus horas de ocurrencia difieren ≤ 30 s y sus epicentros ≤ 100 km. Dos informes de la misma fuente nunca se fusionan; un evento tiene como mucho un informe por fuente. La magnitud no decide.
- **FR-005**: id canónico estable: el del primer informe que creó el evento (id USGS tal cual; los de EMSC con prefijo `emsc-`). No cambia cuando se une otra fuente ni con revisiones.
- **FR-006**: fuente principal (de la que salen hora, epicentro, profundidad y magnitud): EMSC dentro de la caja de Europa (lat 34–72, lon −25–45), USGS fuera; si solo hay una, esa.
- **FR-007**: versión del evento fusionado: cambia cuando cambia cualquiera de sus informes o se une uno nuevo, y es siempre mayor que la anterior. La misma entrada produce exactamente el mismo mensaje (determinista).
- **FR-008**: garantías de la fusión: escribe en Kafka antes de confirmar su estado; un fallo provoca una reentrega idéntica que el consumidor descarta; nunca una pérdida.
- **FR-009**: los eventos que ya estaban en la base antes de esta feature se incorporan al estado de la fusión con su id, para que no se dupliquen.
- **FR-010**: relleno: orden puntual que publica en los topics por fuente todos los terremotos M ≥ 2,5 de un intervalo (por defecto 2025-01-01 → ahora) de USGS y EMSC, partiendo cada intervalo según el recuento de la fuente hasta que la consulta cabe, y marcando lo publicado. Repetirlo no republica nada.
- **FR-011**: el consumidor guarda las fuentes de cada evento (estado actual e historial); la API las devuelve; el panel las muestra en la ficha y atribuye EMSC.
- **FR-012**: el modo `replay`, la prueba de humo y los casos sintéticos siguen funcionando (contrato v1).
- **FR-013**: la comparación histórica compara la misma fuente: base de 2025 de USGS y, en las últimas 24 h, solo los eventos con `usgs` entre sus fuentes. Enunciado §7.

### Key Entities

- **Informe**: lo que dice una fuente de un terremoto (fuente, id de origen, versión, hora, epicentro, profundidad, magnitud, lugar, original).
- **Evento fusionado**: uno o varios informes de fuentes distintas; id canónico, versión, fuente principal.
- **Estado de la fusión**: informes vistos y eventos emitidos (esquema `fusion`), propiedad del servicio de fusión.

## Success Criteria *(mandatory)*

- **SC-001**: en 24 h, Europa pasa de 0 eventos a un número del orden del de EMSC.
- **SC-002**: de los terremotos M ≥ 4 que están en las dos fuentes, ≥ 95 % quedan como un único evento (la medición previa da 97,6 % con la regla elegida; evidencias/umbrales-2025-01-m4.txt).
- **SC-003**: ningún id canónico repetido; ningún par de eventos de fuentes distintas a ≤ 30 s y ≤ 100 km que no esté fusionado (salvo el caso de un evento con dos candidatos de la misma fuente).
- **SC-004**: parar la fusión a mitad de un lote y volver a arrancar no cambia los recuentos finales.
- **SC-005**: el relleno de 2025–2026 termina sin consultas truncadas (cada intervalo por debajo del límite de su fuente).

## Assumptions

- EMSC (seismicportal.eu) mantiene su servicio FDSN gratuito y sin clave, con licencia CC BY 4.0.
- La comparación con 2025 sigue usando la base histórica de USGS (M ≥ 4) y, para comparar la misma fuente, las últimas 24 h cuentan solo los eventos en los que participa USGS. Medido tras el relleno: la unión fusionada da 21.938 eventos M ≥ 4 en 2025 frente a 18.302 de USGS (+20 %, unos 3.800 que solo cataloga EMSC); comparar la unión con la base USGS habría inflado el cociente.
- Los terremotos pequeños de Europa (M < 2,5) solo entran en directo, no por el relleno.

## Fuera de alcance

- ISC, INGV, GEOFON y AFAD.
- WebSocket de EMSC (se usa sondeo).
- Pedir histórico automáticamente cuando un filtro no encuentra nada.
- Recalcular la pertenencia de un informe a un evento cuando una revisión lo mueve.
