# Tareas 008

- [x] T1 `puro/globo.ts` + `puro/globo.spec.ts`: puntos, anillos, color del anillo, etiqueta escapada (AC-1)
- [x] T2 `componentes/globo/{globo.ts,globo.html,globo.css}`: globe.gl con carga dinámica, datos, selección,
  giro, movimiento reducido, sin WebGL (FR-002 a FR-007)
- [x] T3 `componentes/mapa/{mapa.ts,mapa.html,mapa.css}` + spec: selector «Plano / Globo 3D» (FR-001)
- [x] T4 Verificación: Vitest, build con chunk separado y capturas en `specs/008-globo/evidencias/` (AC-2, AC-3)

## Resultado de T4 (08/11/2026)

- Vitest: 26 ficheros, 284 tests en verde.
- `npm run build`: carga inicial 500 kB (126 kB comprimido); globe.gl va en un chunk diferido `globe-gl` de
  2,01 MB (450 kB comprimido) que solo se descarga al pulsar «Globo 3D». Presupuestos de `angular.json`
  subidos a 550 kB (inicial) y 6 kB (estilos de componente) para el selector.
- Navegador (Chromium del IDE, API local con 484 eventos reales):
  - `02-globo-pulsos.png`: globo con tierra oscura, puntos por profundidad y pulsos por magnitud; los
    controles de Leaflet quedan ocultos debajo.
  - `03-seleccion-chile.png`: «Ver en el mapa» en la tabla con el globo activo gira hasta el evento
    `us7000twxf` (M 4,7, Chile), lo marca en amarillo y su pulso sale naranja.
  - `01-primer-intento-tierra-clara.png`: primera versión, descartada porque los anillos no se veían.
- No comprobado en navegador: el aviso sin WebGL y el modo de movimiento reducido (solo por código).

## T5 Optimización (08/11/2026)

Medido en el Chromium del IDE, globo girando con 489 eventos (dev server, `devicePixelRatio` 1):

| | fps | peor fotograma | bloqueado al abrir | llamadas de dibujo |
|---|---|---|---|---|
| Antes | 21 | 61 ms | 2644 ms | 4212 |
| Después | 165 | 6 ms | 177 ms | ~600 |

- El perfil de CPU señalaba `getParameters`/`getProgram` de three.js: un objeto 3D por cada parte de país
  (tapa, lateral y borde), unas 3600 llamadas de dibujo por fotograma. Quitando solo los polígonos se pasaba
  a 165 fps; anillos y puntos apenas influían.
- La tierra y las fronteras se pintan una vez en una textura equirectangular de 4096 × 2048 (canvas 2D) y se
  aplican al globo: una sola llamada de dibujo.
- `public/datos/paises-globo.geojson` (241 kB, 16 701 vértices) sustituye al catálogo de 2,3 MB solo para
  dibujar; se regenera con `npm run fronteras:globo`. La asignación de país no cambia.
- Además: `pixelRatio` ≤ 1,5, animación en pausa si el globo sale de la vista o la pestaña se oculta, y
  geometrías de puntos y anillos más ligeras.
- Evidencia: `evidencias/04-globo-optimizado.png`.
