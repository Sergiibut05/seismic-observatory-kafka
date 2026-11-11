# Quickstart 011

## Prerrequisitos

Panel 006–010 funcionando: `docker compose up -d`, `cd frontend; npm ci; npm start` contra `http://127.0.0.1:8000`.

## Comprobar

1. `cd frontend; npm test`: Vitest en verde, incluidos `mundo`, `tinta`, `tema.service`, `panel-ui.store` y el contraste.
2. Ventana privada: tema papel, cabecera en una línea, mapa sin teselas con la paleta del globo.
3. Botón de tema (arriba a la derecha): a noche, una gota de tinta de borde ondulado nace en el botón y cubre la ventana; a papel, se recoge hacia el botón. Al terminar no queda nada a medias. Recargar: el tema se conserva.
4. Ampliar una región y pulsar «Globo 3D»: la escena crece desde el marco del mapa, centrada en esa región. Girar y volver a «Plano»: se encoge hacia el marco y el plano se centra en lo que miraba el globo.
5. En el globo: pulsar un país (realce neutro) y cambiar de tema con el globo abierto (cambia de paleta, la cámara no se mueve).
6. Bajar a los bloques de análisis: la comparación muestra dos barras y el cociente con su lectura en palabras; Recuentos y Distribuciones van a todo el ancho con dos gráficas cada uno. Pasar el ratón por la gráfica por hora: ficha con hora y eventos; el resto se atenúa. Cambiar «País» por «Subregión» en el segmentado.
7. Pestaña de red: sin peticiones a terceros por fuentes ni teselas; `npm run build` deja las fuentes en `dist/panel/browser/media/`.

## Evidencias

`evidencias/`: plano en papel, bloques de análisis en papel y globo de noche con un país pulsado. La transición de tinta se comprueba con el test de `tinta` y pausando la animación en el navegador.
