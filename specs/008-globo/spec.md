# Feature 008: globo 3D con pulsaciones

Ampliación sobre el mínimo del enunciado: el mapa plano de Leaflet (§8) sigue siendo la vista por defecto y la
de referencia. Esta feature añade una vista alternativa en 3D. Pedida por el usuario el 2026-11-08.

## Requisitos

- **FR-001.** El bloque «Mapa de eventos» ofrece un selector «Plano / Globo 3D». Por defecto, «Plano». Cambiar de
  vista no cambia los filtros ni pide datos nuevos: el globo usa la misma respuesta de `/eventos/mapa`.
- **FR-002.** En el globo, cada evento es un punto con el mismo color de profundidad que el mapa plano y una
  altura que crece con la magnitud. Si la magnitud o la profundidad faltan, se dibuja en gris (ND) y nunca se
  trata como 0.
- **FR-003.** Los eventos más recientes del filtro (60 como máximo) emiten anillos que se abren y se desvanecen
  (pulsaciones). El radio máximo y el color del anillo (ámbar, naranja, rojo) crecen con la magnitud.
- **FR-004.** Al pasar el ratón por un punto aparece su magnitud, el lugar y la hora UTC. El texto de la API se
  escapa siempre: nunca se interpreta como HTML. Pulsar un punto selecciona el evento (la tabla lo resalta) y
  centra el globo en él; elegir un evento en la tabla también lo centra.
- **FR-005.** El globo gira despacio hasta que el usuario lo toca. Con `prefers-reduced-motion` no gira y no hay
  pulsaciones.
- **FR-006.** Sin WebGL, el globo muestra un aviso y deja el mapa plano como alternativa. La librería se carga
  solo al abrir el globo, así que la carga inicial del panel no crece.
- **FR-007.** Sin recursos externos nuevos: las fronteras salen de `datos/paises.geojson` (ya en el panel) y no
  hay texturas de terceros ni tokens.

## Criterios de aceptación

- **AC-1.** Vitest cubre el escape de HTML de la etiqueta, la selección y el tamaño de los anillos, el color ND
  y el modo sin movimiento.
- **AC-2.** En un navegador real, captura del globo con pulsaciones y de un punto seleccionado.
- **AC-3.** `npm run build` sin errores, y el chunk de globe.gl separado del bundle inicial.

## Fuera de alcance

Dibujar los eventos bajo la superficie a su profundidad real, relieve, texturas satelitales y animaciones en el
tiempo (línea temporal).
