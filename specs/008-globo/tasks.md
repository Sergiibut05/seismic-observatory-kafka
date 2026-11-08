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
