# Tareas 010

## Fase 1 — Spec (hecho)

- [x] T0 spec.md, plan.md, research.md, data-model.md, contracts/ui.md, quickstart.md, checklist

## Fase 2 — Lógica pura (P1, bloquea el globo)

- [x] T1 `puro/globo.ts` + `puro/globo.spec.ts`: `alturaColumna`, `colorPulso` violeta, `recortarPorHora`, `marcasCinta`, `paisEnPunto`, `barrasEscena`. Actualizar specs ámbar. (US2, AC-1)

## Fase 3 — Encuadre del panel (P2 / US3, se puede hacer en paralelo a T1)

- [x] T2 `nucleo/panel-ui.store.ts`: `enGlobo`, `superficie`, `filtrosAbiertos`, `campoFoco`
- [x] T3 `componentes/frase-filtros/` y `componentes/superficies/` + i18n es/en (borrar `globo.leyenda_pulsos` y `globo.pista`; ampliar `globo.aria`)
- [x] T4 `app.html` / `app.css` / `app.ts` / `styles.css`: clases de rejilla, mapa a `100svh` en escritorio, superficies en móvil, diálogo de filtros. `filtros/` modo overlay. `mapa.ts` lee `enGlobo` del store. Tests de app, mapa y filtros. (US3, FR-008)

## Fase 4 — Escena (P1 / US1–US2)

- [x] T5 Dependencia `three` exacta. `componentes/globo/mallas.ts` (InstancedMesh + aro blanco), import dinámico en `iniciar()`
- [x] T6 `globo.html/css/ts`: pantalla completa, leyenda gráfica, cinta, cifra, gráfica conmutable, polígono de país, `htmlElementsData` de magnitud, `ringsData` violeta, fondo `#070B12`. (FR-001 a FR-007, FR-009, FR-010)

## Fase 5 — Verificación

- [x] T7 `npm test` y `npm run build` (chunks diferidos). Capturas en `evidencias/` si hay navegador: globo a sangre y plano móvil. (AC-2, AC-3)

## Orden

T0 → T1 y T2 en paralelo → T3 → T4 → T5 → T6 → T7.

T4 no espera a T1. T6 espera T1 y T5. T7 espera el resto.
