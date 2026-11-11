# Quickstart 010

## Prerrequisitos

Panel 006–009 funcionando: `docker compose up -d`, `cd frontend; npm ci; npm start` contra `http://127.0.0.1:8000`.

## Comprobar

1. `cd frontend; npm test` — Vitest verde, incluidos `globo.spec.ts` (violeta, altura, recorte) y el conmutador de superficies.
2. `npm start`. En escritorio: mapa a alto de ventana, filtros fijos al bajar. En ~360 px: frase + Mapa/Tabla/Análisis; una superficie cada vez.
3. «Globo 3D»: escena a sangre, frase, leyenda de tres tamaños, cinta, cifra. Arrastrar la cinta oculta eventos recientes sin nueva petición en red. Clic en país ilumina el polígono. Selección: magnitud anclada y aro blanco.
4. «Plano»: la rejilla vuelve y el recorte no persiste.
5. `npm run build` — chunk de globe.gl / three diferido, no en la carga inicial.

## Evidencias

Capturas en `specs/010-escena/evidencias/` (globo a pantalla completa y plano móvil).
