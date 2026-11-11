# Feature Specification: identidad visual «papel y tinta»

**Feature Branch**: `011-identidad`

**Created**: 2026-11-11

**Status**: Implementada

**Input**: El panel funciona, pero se parece a cualquier cuadro de mandos oscuro hecho con IA (fondo negro, acento violeta, paneles de vidrio). Es un proyecto de clase y más de veinte equipos entregan el mismo enunciado: el panel necesita una identidad propia y un acabado más integrado. En concreto, el paso de plano a globo «se ve mal», las gráficas son mejorables y la cabecera tiene demasiado texto. Se pide un modo claro de papel por defecto, un modo noche con la paleta actual y una transición de tinta entre ambos. En una segunda vuelta el usuario pidió rehacer esa transición y dar más acabado a los bloques de comparación, recuentos y distribuciones.

Ampliación sobre 006, 008 y 010. El enunciado §8 sigue cubierto bloque a bloque: cambia el aspecto, no los bloques ni la API.

## Cambios respecto a specs anteriores

- **006 (mapa base)**: se retiran las teselas de OpenStreetMap. El plano dibuja el mismo Natural Earth que el globo.
- **006 FR-015 (tipografía del sistema)**: pasa a IBM Plex (Sans, Serif, Mono) servida desde el bundle; se mantiene «sin CDN».
- **008 / 010 (globo)**: columnas más cortas y con contorno de tinta; pulsos en rojo de pluma en lugar de violeta; país pulsado con realce neutro; leyenda de columnas en lugar de círculos.
- **010 (encuadre)**: el cambio plano ↔ globo conserva la región mirada y se anima con un recorte desde el marco del mapa.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un panel con identidad propia (Priority: P1)

Quien abre el panel ve una hoja de papel: tinta para el texto, una serif para la marca y los títulos, cifras en mono, rojo de pluma solo para lo que importa. Los controles son píldoras suaves; la cabecera cabe en una línea; plano y globo dibujan el mismo mundo.

**Independent Test**: abrir el panel sin preferencia guardada a 1440 px: tema papel, cabecera en una línea, mapa visible sin bajar, ningún violeta ni desenfoque.

**Acceptance Scenarios**:

1. **Given** un navegador sin preferencia guardada, **When** se abre el panel, **Then** se muestra el tema papel.
2. **Given** la cabecera, **When** se lee, **Then** cada dato lleva un rótulo corto (API, USGS, Periodo, Eventos) y un valor corto; el nombre largo sigue para lectores de pantalla y el instante completo en el `title`.
3. **Given** el plano, **When** se mira el mapa, **Then** usa la misma geometría y paleta que el globo y no pide teselas a terceros.

---

### User Story 2 - Modo noche con transición de tinta (Priority: P1)

Un botón en la cabecera cambia entre papel y noche. Al pasar a noche, la tinta nace en el botón como una gota de borde ondulado y se derrama hasta cubrir la ventana; al volver a papel, la misma gota se recoge hacia el botón. Al terminar no queda nada a medias. La elección se recuerda.

**Independent Test**: pulsar el botón en los dos sentidos; pausar la animación a mitad y leer el recorte; recargar.

**Acceptance Scenarios**:

1. **Given** el tema papel, **When** se pulsa el botón de tema, **Then** la página pasa a noche con la gota de tinta (≈ 0,9 s); al pulsarlo otra vez, la tinta se recoge hacia el botón.
2. **Given** un fotograma cualquiera, **When** se mira, **Then** hay una sola mancha, de borde nítido, sin islas del tema viejo ni agujeros.
3. **Given** `prefers-reduced-motion` o un navegador sin transiciones de vista, **When** se cambia de tema, **Then** el cambio es inmediato.
4. **Given** el globo abierto, **When** se cambia de tema, **Then** el globo cambia de paleta sin recargar datos ni mover la cámara.

---

### User Story 3 - Plano y globo, un solo mundo (Priority: P1)

Al pasar al globo, la escena se descubre desde el marco del mapa hasta llenar la ventana, centrada en lo que se miraba; al volver, se encoge hacia el marco y el plano se centra en lo que miraba el globo.

**Acceptance Scenarios**:

1. **Given** el plano ampliado sobre una región, **When** se pulsa «Globo 3D», **Then** esa región queda en el centro de la escena.
2. **Given** un fotograma intermedio, **When** se mira, **Then** no conviven dos cabeceras ni hay una imagen del mapa estirada.
3. **Given** el globo en una pantalla vertical, **When** se abre, **Then** cabe entero a lo ancho.

---

### User Story 4 - Bloques de análisis con más acabado (Priority: P2)

La comparación histórica se lee de un vistazo: dos barras sobre la misma escala (últimas 24 h y media diaria de 2025) y, al lado, el cociente en grande con su lectura en palabras. Recuentos y distribuciones ocupan todo el ancho, con dos gráficas lado a lado, y cada gráfica lleva encima sus datos clave. Las barras son finas, de un solo tono, con el extremo redondeado; el texto no se encoge con la gráfica. Al pasar el ratón aparece una ficha con el valor y el resto se atenúa.

**Acceptance Scenarios**:

1. **Given** la gráfica por hora, **When** se pasa el ratón por una barra, **Then** aparece una ficha con la hora y sus eventos y las demás se atenúan.
2. **Given** ceros, sin valor y ND, **When** se dibujan, **Then** se distinguen como en 006 y la tabla equivalente sigue disponible.
3. **Given** la comparación con el histórico cargado, **When** se lee, **Then** el cociente va acompañado de «n % por debajo / por encima de la media diaria», en tinta neutra (describe, no valora).
4. **Given** la distribución de profundidad, **When** se mira el eje, **Then** cada intervalo lleva el color que tiene en el mapa.
5. **Given** un ancho cualquiera, **When** se dibuja una gráfica, **Then** sus textos miden lo mismo que el resto del panel (el lienzo no se escala).

---

### Edge Cases

- `localStorage` bloqueado: el tema funciona en la sesión y vuelve a papel al recargar.
- Falla `paises.geojson`: el plano muestra océano y círculos, con el aviso de fronteras de 006.
- Profundidad 0–10 km (amarillo claro) sobre papel: círculos y columnas llevan contorno de tinta.
- Cambio de tema con un país iluminado: el polígono adopta la paleta nueva.
- Puntero táctil: sin hover; el valor de la barra máxima y la tabla siguen disponibles.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: dos temas, `papel` (por defecto) y `noche`, con los mismos tokens CSS. Ningún componente fija colores fuera de los tokens, salvo la escala de profundidad (fuente única `escalas.ts`).
- **FR-002**: botón de tema junto al idioma, con nombre accesible y `aria-pressed`; la elección se guarda y se aplica antes del primer pintado.
- **FR-003**: transición de tinta: una gota de borde ondulado (`clip-path`) que crece desde el botón hasta cubrir la ventana al pasar a noche y se recoge hacia él al volver a papel; solo crece (o solo mengua), sin restos al terminar, ≈ 0,9 s. Inmediata con movimiento reducido o sin `startViewTransition`.
- **FR-004**: IBM Plex Serif (marca y títulos), Sans (texto) y Mono (cifras), subconjunto latino, desde el bundle.
- **FR-005**: formas suaves: tarjetas de 12 px, controles de 8 px, segmentados en píldora con la opción elegida levantada, botones en píldora, rótulos sin mayúsculas forzadas. El rojo de pluma solo para acentos, selección y alertas.
- **FR-006**: cabecera en una línea: rótulos cortos e instantes sin año ni segundos; subtítulo de directo y ayuda del interruptor de sintéticos fuera de la vista (siguen para lectores y en `title`).
- **FR-007**: un solo mundo: plano y globo con la misma geometría (Natural Earth 1:50m) y la misma paleta por tema; el plano sin teselas.
- **FR-008**: vista compartida: el globo se abre en el centro y zoom del plano y el plano vuelve al centro del globo (también si giraba solo). Zoom inicial del plano según el ancho; en vertical, el globo se aleja para caber.
- **FR-009**: transición plano ↔ globo por recorte (`clip-path`) desde y hacia el marco del mapa, sin fundido. Lo que se revela está siempre completo: al entrar, el globo con su textura y sus columnas; al salir, el plano ya reencuadrado. Mientras dura la transición se ignoran nuevas pulsaciones.
- **FR-010**: globo: columnas con altura cuadrática acotada (M7 < 0,2 radios) y contorno de tinta; pulsos rojos por tema; aro de selección por tema; país pulsado con realce neutro; leyenda de columnas; paneles de la escena como láminas de papel; cinta fina con la pluma roja.
- **FR-011**: gráficas de barras de un solo tono (`--barra`), extremo redondeado, rejilla de filete continuo, valor solo en la máxima (verticales) o en la punta de cada barra (lista ordenada), ficha al pasar el ratón, atenuación del resto y entrada animada. El lienzo mide lo que su contenedor (1 unidad = 1 px).
- **FR-013**: comparación histórica como dos barras sobre la misma escala y el cociente destacado con su lectura en palabras; nunca con colores de estado.
- **FR-014**: Recuentos y Distribuciones a todo el ancho, con dos partes lado a lado si caben; cada parte muestra sus datos clave (total, países o subregiones, hora punta, media por hora, intervalo más frecuente). La lista por país da la parte del total de cada categoría; la gráfica por hora, la línea de la media; la de profundidad, los colores del mapa bajo el eje. El agrupamiento país / subregión es un control segmentado.
- **FR-012**: contraste ≥ 4,5:1 del texto y ≥ 3:1 de bordes y marcas en los dos temas, comprobado en test.

### Key Entities

- **Tema**: `papel` | `noche`; preferencia de interfaz, no viaja a la API.
- **VistaMundo**: `lat`, `lng`, `zoom`; compartida entre plano y globo, no es estado de filtros.
- **PaletaMundo**: océano, tierra, frontera, retícula, contorno de círculo, fondo de escena, selección y realce de país, por tema.

## Success Criteria *(mandatory)*

- **SC-001**: en el panel no queda ningún `backdrop-filter` ni el violeta del acento anterior.
- **SC-002**: el cambio de tema completo (incluido el globo abierto) no hace peticiones a la API.
- **SC-003**: en fotogramas intermedios de las dos transiciones no hay doble exposición ni manchas sueltas.
- **SC-004**: test de contraste de los tokens de los dos temas en verde.
- **SC-005**: la carga no hace peticiones a terceros por fuentes ni por teselas.
- **SC-006**: la cabecera de escritorio cabe en una línea a 1440 px.

## Assumptions

- Contrato de la API y servicios de Compose sin cambios.
- La escala de profundidad no cambia: es la del enunciado y la de la leyenda.

## Fuera de alcance

Sonificación, temas adicionales, librerías de gráficos (las gráficas siguen siendo SVG propio), cambios en el contenido de la ficha de Leaflet y de la tabla. Sin teselas, el plano no muestra ciudades ni carreteras al ampliar: es una decisión aceptada.
