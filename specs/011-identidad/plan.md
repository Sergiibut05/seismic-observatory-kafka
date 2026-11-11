# Plan 011: identidad visual «papel y tinta»

- **Rama**: `011-identidad` | **Spec**: [spec.md](./spec.md)
- **Stack**: el del panel (Angular 21, Vitest, Leaflet, globe.gl 2.46.2). Nuevas dependencias: `@fontsource/ibm-plex-sans`, `-serif` y `-mono` 5.3.0 (OFL 1.1), solo CSS y fuentes.
- **Contrato**: no se toca. Ninguna petición nueva a la API.

## Decisiones

1. **Tokens por tema** en `styles.css`: `:root[data-tema='papel']` (también `:root`) y `:root[data-tema='noche']`. Nombres semánticos (`--fondo`, `--tinta`, `--acento`, `--barra`, `--segmento-*`, `--lamina-*`, `--mundo-*`). Clase global `.lamina` para paneles sobre el mundo.
2. **`TemaService`** (`nucleo/tema.service.ts`): señal `tema`, `localStorage` con `try/catch`, `data-tema` en `<html>`. Un script en `index.html` aplica el tema guardado antes del primer pintado (no hay CSP que lo impida).
3. **Transición de tinta** (`puro/tinta.ts`): `startViewTransition` sin animación CSS en las raíces; `Element.animate` de `clip-path: polygon(…)` con los fotogramas de `fotogramasTinta` (96 vértices, 28 fotogramas, 0,9 s) sobre la raíz nueva al pasar a noche (`html.tema-derrama`) o, al revés, sobre la vieja al volver a papel (`html.tema-recoge`, con `z-index` encima). La gota solo crece: radio = `avance(p)` × radio final × ondulación acotada a ±11 %. Durante el cambio, `html.cambiando-tema` mete todo en la instantánea raíz; al terminar se cancela la animación.
4. **Un solo mundo** (`puro/mundo.ts`): `PALETAS_MUNDO[tema]`; el plano quita `L.tileLayer`, pinta `paises.geojson` opaco y una retícula de 30°; el globo genera su textura con la misma paleta y la regenera al cambiar de tema.
5. **Vista compartida** (`PanelUiStore.vistaMundo`, no señal): se escribe en `moveend` del plano y al soltar la cámara del globo; `capturarVista` cubre el giro automático. Conversión pura `altitudDesdeZoom`, `zoomDesdeAltitud`, `altitudParaAncho`, `zoomParaAncho`.
6. **Transición plano ↔ globo** (`PanelUiStore.fijarGlobo`): `startViewTransition` sin animación CSS en las raíces; `Element.animate` de `clip-path: inset(… round 12px)` sobre la raíz nueva (entrar) o la vieja (salir, con `z-index` encima). `recorteDesde` es puro.
7. **Globo** (`componentes/globo/`): `alturaColumna` cuadrática; `mallas.ts` con una malla instanciada de columnas y otra de contorno (casco invertido) y luces atenuadas en papel; `colorPulso(m, tema)`; realce de país desde la paleta.
8. **Gráficas** (`componentes/grafico-barras/`): `caminoBarra` (extremo redondeado), zona de puntería como `path` (los `rect` siguen siendo solo marcas de datos), eventos de puntero en el `<g>`, tooltip dentro del SVG.
9. **Cabecera**: `formatearCortoUtc`; `dt` fuera de la vista y rótulo corto por CSS con texto alternativo vacío.
10. **Contraste en test**: `puro/contraste.ts` + `styles.contraste.spec.ts`, que lee `styles.css` y comprueba los pares de los dos temas (texto, bordes, foco, avisos, barras).

## Constitución

- I–VII, IX: no aplican (no hay Compose, Kafka ni secretos nuevos).
- VIII Simplicidad y evidencia: sin librerías de gráficos ni de animación; las dependencias nuevas son solo fuentes. Se quita un tercero (teselas OSM). Evidencia: tests puros, de contraste y capturas.

## Estructura

```text
frontend/src/
  index.html                       # tema antes del primer pintado
  styles.css                       # tokens papel / noche, segmentado único, transiciones
  app/
    nucleo/tema.service.ts
    nucleo/panel-ui.store.ts       # vistaMundo, capturarVista, recorte plano ↔ globo
    puro/tema.ts | mundo.ts | tinta.ts | contraste.ts | formato.ts (formatearCortoUtc)
    puro/globo.ts                  # alturaColumna, colorPulso(m, tema)
    componentes/globo/             # paleta por tema, mallas con contorno
    componentes/mapa/              # sin teselas, paleta por tema
    componentes/grafico-barras/    # lienzo a tamaño real, barras redondeadas, ficha, cuota, referencia, clave de color
    componentes/estado/            # cabecera compacta
```

## Pruebas

- Vitest: `mundo` (zoom ↔ altitud, encuadre), `tinta` (mismos vértices en todos los fotogramas, nace en el botón, solo crece, cubre la ventana al terminar), `tema.service` (por defecto, persistencia, almacenamiento bloqueado), `panel-ui.store` (`recorteDesde`), contraste, `globo` (altura, pulsos por tema); specs de 006–010 sin cambios de comportamiento.
- Navegador: papel y noche, plano y globo, 1440 px y 390 px; las dos transiciones congeladas en fotogramas intermedios; `npm run build` sin peticiones a terceros.
