# Plan 008: globo 3D

- **Librería.** `globe.gl` 2.46.2 (MIT, sobre three.js), versión exacta. Se carga con `import()` dinámico al
  elegir «Globo 3D». Es una dependencia nueva fuera del stack mínimo y está aceptada como ampliación (spec).
- **Lógica pura.** En `puro/globo.ts`:
  - `puntosGlobo(features)` y `anillosGlobo(features, max)`: ordena por `ocurrencia` descendente, como máximo 60
    anillos, con radio `2,5 + 1,5·M` grados acotado a [2,5, 14] y dos ondas concéntricas a la vez.
  - `colorPulso(M)`: ámbar < 4, naranja 4–6, rojo ≥ 6, gris si ND. Se separa del color de profundidad porque
    el amarillo claro no se veía sobre la tierra (captura `evidencias/01-primer-intento-tierra-clara.png`).
  - `colorAnillo(hex)`: devuelve `t ⇒ rgba` con opacidad `1 − t`.
  - `etiquetaGlobo(p)`: HTML con todos los valores escapados por `escaparHtml`.
  - El color de profundidad se reutiliza de `estiloCirculo`.
- **Componente.** `componentes/globo/` con `ViewEncapsulation.None`, como el mapa.
  - Usa `PanelDatosService.mapa()` y `FiltrosStore.eventoSeleccionado` mediante `effect`.
  - Un `ResizeObserver` ajusta `width`/`height`; `_destructor()` libera WebGL al destruir.
  - En jsdom no se inicia, con el mismo `MAPA_HABILITADO`.
- **Integración.** En `componentes/mapa/`: selector con `aria-pressed`. El globo se superpone dentro de
  `.mapa-marco`, así que Leaflet sigue vivo debajo y la selección no se pierde. La leyenda plana se oculta en 3D.
- **Estilo.**
  - Paleta: océano `#16324a`, tierra `#d9e2d0` con borde `#5b6b78`, fondo `#0d1b2a` y atmósfera `#8fbcd4`.
  - La pulsación es el único movimiento de la página, en línea con la skill de diseño: un solo momento de
    movimiento, con significado.
