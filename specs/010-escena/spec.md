# Feature Specification: escena del globo y panel responsive

**Feature Branch**: `010-escena`

**Created**: 2026-11-09

**Status**: Draft

**Input**: Convertir el modo Globo 3D en una escena a pantalla completa, con marcas propias, leyenda dibujada, cinta de tiempo y comparación en la escena; reencuadrar también el panel plano para móvil y escritorio. El contrato de la API no cambia.

Ampliación sobre 008. El enunciado §8 sigue cubierto: mapa, tabla, filtros, comparación, recuentos, distribuciones, estado y nota de riesgo permanecen; cambia su encuadre y, en el globo, el acento visual. Pedida el 2026-11-09.

## Cambios respecto a spec 008

- **FR-003 (anillos)**: el pulso deja de ser ámbar/naranja/rojo. Pasa a violeta eléctrico (bajo / medio / alto). El cuerpo del terremoto sigue la escala de profundidad del mapa plano.
- **Fuera de alcance de 008 (cinta temporal)**: la cinta de 24 h es requisito de esta feature. Recorte local; no hay filtro nuevo en la API y el tope de `/eventos/mapa` sigue en 5000.
- El plano sigue siendo la vista por defecto y la de referencia del enunciado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Escena a pantalla completa (Priority: P1)

Quien elige «Globo 3D» ve la Tierra a sangre bajo la cabecera, no un bloque más del cuadro de mandos. Arriba, una frase con el modo, la magnitud, el país y la ventana; cada trozo abre el formulario de filtros que ya existe, sin un panel permanente. Abajo, leyenda gráfica (tres tamaños y tira de profundidad), cinta de tiempo, cifra de comparación y una sola gráfica.

**Why this priority**: es el cambio de encuadre que justifica la feature; sin él el globo sigue siendo la misma tarjeta.

**Independent Test**: abrir el globo, comprobar que ocupa la ventana bajo la cabecera, que la frase abre filtros y que al volver a «Plano» reaparece la rejilla.

**Acceptance Scenarios**:

1. **Given** el panel en plano, **When** se pulsa «Globo 3D», **Then** la escena ocupa el alto bajo la cabecera y tabla, recuentos y fichas de análisis no se ven.
2. **Given** la escena abierta, **When** se pulsa un trozo de la frase, **Then** se abre el control de filtro correspondiente (el mismo formulario, no uno nuevo).
3. **Given** la escena, **When** se pulsa «Plano», **Then** vuelve la rejilla del panel y el recorte de la cinta desaparece.

---

### User Story 2 - Marcas, país y cinta (Priority: P1)

Cada evento es una columna cuya altura crece con la magnitud; nulo no inventa altura y el cuerpo queda en gris ND. Los 60 más recientes emiten dos ondas violeta. El elegido muestra la magnitud grande junto al punto («ND» si falta) y un aro blanco (ya no amarillo). Pulsar un país enciende su polígono y, si el código está en las opciones, escribe el filtro de país. Al borde, una cifra: eventos del filtro frente a la media diaria de 2025; en REPRODUCCIÓN, la etiqueta «REPRODUCCIÓN». Mover la cinta oculta en globo y gráfica de la escena lo posterior a esa hora.

**Why this priority**: es lo que se ve y se prueba en el globo; la lógica de altura, color y recorte se verifica sin WebGL.

**Independent Test**: tests puros de altura, paleta violeta, ND y recorte; en navegador, captura de columnas, pulso, país iluminado, magnitud anclada y cinta.

**Acceptance Scenarios**:

1. **Given** eventos con magnitud 2, 5 y 7 y uno sin magnitud, **When** se calculan las alturas, **Then** crecen con la magnitud y el nulo no usa la altura de un 0 inventado; el cuerpo ND es gris.
2. **Given** la cinta al final, **When** se arrastra hacia un instante anterior, **Then** desaparecen del globo y de la gráfica de la escena los eventos posteriores a esa hora, sin nueva petición a la API.
3. **Given** un clic en un país del catálogo dibujable, **When** su `ADM0_A3` está entre las opciones, **Then** se ilumina ese polígono y el filtro de país pasa a ese código. «Sin país asignado» no tiene polígono.

---

### User Story 3 - Panel plano usable en móvil y escritorio (Priority: P2)

En escritorio el mapa usa el alto de la ventana bajo la cabecera y los filtros quedan fijos a un lado. En una pantalla estrecha una frase resume los filtros y un conmutador muestra una superficie cada vez: Mapa, Tabla o Análisis. Análisis apila comparación, recuentos, distribuciones y la nota de riesgo. El orden del DOM no cambia. La cabecera de estado y la franja «REPRODUCCIÓN» siguen visibles.

**Why this priority**: el usuario pidió que toda la app fuera usable en el móvil, no solo el globo; el enunciado §8 sigue leyéndose en esas superficies.

**Independent Test**: a menos de 48 rem, el conmutador oculta las otras superficies; a 72 rem o más, filtros fijos y mapa a alto de ventana; tabla y gráficos siguen en el DOM.

**Acceptance Scenarios**:

1. **Given** un ancho de móvil, **When** se elige «Tabla», **Then** se ve la tabla y no el mapa ni el análisis; elegir «Análisis» apila comparación, recuentos, distribuciones y la nota.
2. **Given** escritorio (≥ 72 rem), **When** se mira el plano, **Then** los filtros permanecen a la vista al bajar a la tabla y el mapa ocupa el alto bajo la cabecera.
3. **Given** cualquier superficie, **When** se recorre con teclado, **Then** el orden sigue siendo filtros → mapa → tabla → gráficos.

---

### Edge Cases

- Sin WebGL: aviso y alternativa «Plano», como en 008.
- `prefers-reduced-motion`: ni giro ni ondas; la cinta se mueve sin transición.
- Comparación no cargada o `null`: la cifra de la escena dice «no disponible», nunca 0.
- País pulsado que no está en las opciones: se ilumina el polígono y no se escribe el filtro.
- Magnitud nula en el punto elegido: «ND» junto al punto.
- Cinta con un solo evento o ninguno: la cinta sigue usable; sin marcas si no hay eventos cargados.
- Volver al plano: el recorte local se descarta; el globo no deja filtros a medias.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (ampliación UI, Enunciado §8 intacto): al activar «Globo 3D» la escena ocupa la ventana bajo la cabecera fija. Los demás bloques no se destruyen. El selector Plano / Globo 3D permanece. Por defecto, Plano.
- **FR-002**: frase de filtros activos (modo, magnitud, país, ventana). Cada trozo abre el formulario único de filtros. Sin valor: «–» o «todos», nunca un número inventado.
- **FR-003**: leyenda visible = tres círculos (M2, M5, M7) y la tira de profundidad del mapa plano. Se eliminan las cadenas visibles `globo.leyenda_pulsos` y `globo.pista`. La explicación larga queda en `globo.aria`.
- **FR-004**: columnas con altura según magnitud (función pura). Nulo: sin altura inventada, cuerpo gris ND. Una sola malla instanciada, cargada solo al abrir el globo. Ondas violeta en los 60 más recientes (bajo `#8B7CFF`, medio `#5B4DFF`, alto `#F2F0FF`). Fondo de escena `#070B12`. Selección: aro blanco; se retira `#ffd166` del globo (sigue como foco de la cabecera).
- **FR-005**: un polígono de `paises-globo.geojson` para el país elegido. El país del dato sigue saliendo del backend. Cifra al borde: ventana del filtro frente a la media diaria de 2025, leída de la comparación ya pedida, con el aviso de periodo incompleto en corto. En REPRODUCCIÓN: etiqueta «REPRODUCCIÓN», sin media de 2025.
- **FR-006**: magnitud del evento elegido en HTML anclado a su latitud y longitud; «ND» si falta.
- **FR-007**: cinta local de 24 h con una marca por evento cargado. Moverla recorta globo y gráfica de la escena. El estado no vive en los filtros ni en la API. Al volver al plano, el recorte desaparece.
- **FR-008** (Enunciado §8): panel plano responsive. Móvil: una superficie (Mapa / Tabla / Análisis) y frase que abre el formulario. Escritorio (≥ 72 rem): filtros fijos, mapa a alto de ventana. Un solo `app-filtros`. `styles.css` y `app.css` se reabren en esta feature.
- **FR-009**: una sola gráfica en la escena (hora, magnitud o profundidad), reutilizando el gráfico de barras existente. En pantallas estrechas nace cerrada. En el plano, dentro de Análisis, siguen todos los bloques.
- **FR-010** (008): globe.gl se carga solo al abrir el globo; `prefers-reduced-motion` sin giro ni ondas; sin WebGL, aviso y plano.

### Key Entities

- **Recorte de cinta**: instante local (`corte`); eventos con ocurrencia posterior se ocultan solo en globo y gráfica de escena.
- **País iluminado**: un feature GeoJSON (`ADM0_A3`) distinto del país persistido en el evento.
- **Frase de filtros**: proyección de modo, magnitud, país y ventana desde los filtros ya aplicados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: con el globo activo, quien mira la ventana ve la Tierra a sangre bajo la cabecera, no la rejilla de bloques.
- **SC-002**: un recorte de cinta no provoca petición nueva; el recuento dibujado baja al instante al ocultar lo posterior.
- **SC-003**: en un ancho típico de móvil se llega a mapa, tabla y análisis sin apilar los tres a la vez.
- **SC-004**: nulos de magnitud o profundidad no se leen como 0 en columnas, pulsos ni cifra.
- **SC-005**: la carga inicial del plano no incluye el código 3D del globo (chunk diferido).

## Assumptions

- No se cambia `docs/CONTRATO-API.md` ni los cinco servicios de Compose.
- El catálogo de países del backend no se sustituye; `paises-globo.geojson` solo se dibuja.
- Tipografía del sistema (sin CDN), contraste y foco visible se mantienen (006 FR-015).
- El amarillo `#ffd166` permanece como `--foco-sobre-oscuro` de la cabecera.
- Las columnas van en una sola malla instanciada porque miles de polígonos ya bajaron el globo a ~21 fps en 008.

## Fuera de alcance

Relieve, texturas satelitales, profundidad real bajo la superficie, filtro nuevo en la API, rediseño de la ficha de Leaflet ni de las columnas de la tabla.
