# Tareas 009

- [x] T1 `i18n/{es.ts,en.ts,traducir.ts,i18n.service.ts}` + `i18n/i18n.spec.ts` (AC-1, servicio de AC-2)
- [x] T2 Selector «ES / EN» en la cabecera (`app.html`, `app.ts`, estilos) con `aria-pressed` y `lang` (FR-001, FR-006)
- [x] T3 Funciones puras con `t: Traductor = T_ES` e idioma para números: `formato`, `errores`, `texto-comparacion`,
  `filtros`, `escalas`, `barras`, `globo`, `desactualizado`, `etiqueta-antiguos`, `mapa-ficha` (FR-003, FR-004)
- [x] T4 Plantillas y textos de componentes: estado, filtros, mapa, globo, tabla, comparación, recuentos,
  distribuciones, gráfico de barras, vista de datos, avisos (FR-003, FR-005)
- [x] T5 Repintado de Leaflet y del globo al cambiar de idioma sin pedir datos (FR-002)
- [x] T6 Test de componente: cambio a inglés en cabecera y en un bloque con datos (AC-2); suite completa en verde (AC-3)
- [x] T7 Verificación: `rg` de restos en español, build, captura del panel en inglés en `specs/009-i18n/evidencias/` (AC-4)
  - Hecho sin navegador: `npm run build` correcto (solo los avisos previos de `frame-ticker` y `leaflet` no ESM) y
    `npx ng test --watch=false` con 304 tests en verde (284 previos sin tocar + 20 nuevos).
  - `rg "[áéíóúñ¿¡]" src/app --glob '!*.spec.ts' --glob '!i18n/**'`: fuera de comentarios solo quedan, a propósito:
    `SIN_PAIS = 'Sin país asignado'` (`puro/filtros.ts`, `puro/globo.ts`, `mapa-ficha.ts`: es el dato que envía y recibe la
    API, no texto de pantalla), `AVISO_PERIODO_INCOMPLETO` (`puro/texto-comparacion.ts`: respaldo en español del aviso de la
    API), el `motivo` en español de `validarUrlBase`/`ConfigService` (logs y tests; la pantalla usa la clave del
    diccionario), `nombre: 'Español'` del selector (el nombre de un idioma va en ese idioma) y el valor por defecto
    `etiquetaResto = 'Resto'` de `principalesConResto` (los llamantes pasan la etiqueta traducida).
    También sigue en español `src/index.html` (`<title>` inicial y `meta description`; el título se reescribe al arrancar).
  - Navegador (08/11/2026, Chromium del IDE, API local con 491 eventos reales): sin `localStorage` arranca en español
    (`lang=es`); al pulsar EN cambian cabecera, filtros, mapa, tabla y bloques, `lang=en`, se guarda `idioma=en` y
    **0 peticiones a la API** tras el cambio. Ficha de Leaflet en inglés («Magnitude 4.7 | Chile | Occurrence…»), leyenda
    y leyenda del globo en inglés. Capturas: `evidencias/01-panel-en.png`, `02-ficha-en.png` y `03-globo-en.png`.
  - Arreglo encontrado al verificar: la leyenda del mapa (z-index 650) tapaba la ficha, que vive dentro del panel de
    Leaflet (z-index 400). Ahora la leyenda se oculta mientras la ficha está abierta (`fichaVisible`).
  - Limitación conocida: sin pluralización, en inglés un total de 1 se escribe «1 events».
