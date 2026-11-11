# Research 010

## Paleta violeta frente a profundidad

- **Decisión**: el cuerpo sigue `estiloCirculo`; solo pulso, columna de acento y cifra de magnitud usan violeta (`#8B7CFF` < 4, `#5B4DFF` 4–6, `#F2F0FF` ≥ 6; ND gris `#c8d0d8`).
- **Razón**: el enunciado §8 pide color por profundidad. Mezclar profundidad y pulso en la misma rampa (ámbar de 008) competía con la leyenda y no se leía sobre tierra oscura.
- **Alternativa**: rampa ámbar de 008 — rechazada por la spec.

## Una InstancedMesh, no objectsData por evento

- **Decisión**: `InstancedMesh` añadida a `globo.scene()`, actualizada con `getCoords`.
- **Razón**: 008 midió ~21 fps con un objeto 3D por polígono de país. `customThreeObject` / `objectsData` crearían un mesh por terremoto (hasta 5000).
- **Alternativa**: `pointsData` de globe.gl (008) — se mantiene solo para la etiqueta al pasar el ratón, con radio mínimo, o se sustituye por raycaster; las columnas visibles salen de la malla.

## Cinta local, no query nueva

- **Decisión**: `corte` en el componente globo; `recortarPorHora` puro.
- **Razón**: el contrato no tiene instante de corte y el tope 5000 debe seguir siendo el de la API.
- **Alternativa**: `hasta=` dinámico — provocaría refresco de todos los bloques y rompería la comparación 24 h.

## Rejilla: clases en `main`, no rutas nuevas

- **Decisión**: `rejilla--globo` y `rejilla--mapa|tabla|analisis` en `app.html`.
- **Razón**: el panel es una sola pantalla (006); una ruta destruiría Leaflet y el globo al cambiar.
- **Alternativa**: router con `/globo` — rechazada.

## three como dependencia directa

- **Decisión**: añadir `three` exacto, la mayor `0.x` que cumpla `>= 0.179` resuelta por globe.gl 2.46.2.
- **Razón**: el chunk del globo importa `three` para la malla; sin declaración directa el bundler puede duplicar o romper tipos.
- **Alternativa**: importar three desde el paquete interno de globe.gl — frágil.
