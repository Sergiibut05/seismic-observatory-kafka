# Tareas 011

## Fase 1 — Spec

- [x] T0 spec.md, checklist, plan.md, research.md, data-model.md, contracts/ui.md, quickstart.md

## Fase 2 — Lógica pura (bloquea lo demás)

- [x] T1 [P] `puro/mundo.ts` + spec: paletas por tema, `normalizarLng`, zoom ↔ altitud, encuadre por ancho (FR-007, FR-008)
- [x] T2 [P] `puro/contraste.ts` + `styles.contraste.spec.ts` (FR-012)
- [x] T3 [P] `puro/tinta.ts` + spec: fotogramas de la gota (`clip-path`), solo crece y cubre la ventana (FR-003)
- [x] T4 [P] `alturaColumna` cuadrática y `colorPulso(m, tema)` en `puro/globo.ts`; `formatearCortoUtc` (FR-010, FR-006)

## Fase 3 — Tema y estilo (US1, US2)

- [x] T5 `nucleo/tema.service.ts` + spec; script de `index.html`; botón en la cabecera (FR-002)
- [x] T6 Tokens papel / noche en `styles.css`; `.lamina`; segmentado único en píldora; botones, campos, tablas (FR-001, FR-005)
- [x] T7 Fuentes `@fontsource` en `angular.json` (FR-004)
- [x] T8 Cabecera compacta; frase de filtros; filtros como diálogo; leyenda plegada; comparación como fichas (FR-006)

## Fase 4 — Un solo mundo (US3)

- [x] T9 Mapa sin teselas, retícula, contornos y paleta por tema (FR-007)
- [x] T10b Escena completa al revelar: `precarga.ts`, espera del globo dentro de `startViewTransition`, plano reencuadrado en el callback, recorte inicial y guarda contra pulsaciones dobles (FR-009)
- [x] T10 `PanelUiStore`: `vistaMundo`, `capturarVista`, recorte plano ↔ globo + `recorteDesde` con test (FR-008, FR-009)
- [x] T11 Globo: paleta y textura por tema, columnas con contorno, luces en papel, país neutro, leyenda de columnas, paneles y cinta (FR-010)

## Fase 5 — Gráficas (US4)

- [x] T12 `caminoBarra`, zona de puntería, ficha al pasar el ratón, máxima resaltada, animación de entrada, lienzo a tamaño real (FR-011)
- [x] T12b Comparación con dos barras, cociente y lectura en palabras (`veredictoComparacion`) (FR-013)
- [x] T12c Recuentos y Distribuciones a todo el ancho: datos clave, cuota por país, media por hora, clave de color de la profundidad, segmentado país / subregión (FR-014)

## Fase 6 — Verificación

- [x] T13 `npm test` y `npm run build`; ningún `backdrop-filter` ni violeta (SC-001)
- [x] T14 Navegador: papel y noche, plano y globo, 1440 px y 390 px; transiciones congeladas en fotogramas intermedios. Capturas en `evidencias/`
- [x] T15 README y `FUENTES-Y-LICENCIAS.md` (sin teselas; IBM Plex OFL 1.1; globe.gl y three.js MIT)

## Notas de ejecución

- T3 necesitó tres vueltas (ver research.md): islas por ruido animado; barrido demasiado corto por un umbral mal calibrado; esquina gris y escalonada al final.
- T10: el primer intento con `view-transition-name` producía doble exposición y un mapa estirado; se cambió a recorte.
- T12: los eventos de puntero pasaron de la zona de puntería al `<g>`; la gráfica de la escena heredaba un `--barra` rojo de `globo.css` y se quitó.
- Tras revisar con el usuario se retiraron el titular de 24 h, el helicorder y el estilo cuadrado de instrumento (research.md).

## Orden

T0 → T1–T4 en paralelo → T5 → T6 → T7 → T8 y T9 en paralelo → T10 → T11 → T12 → T13 → T14 → T15.
