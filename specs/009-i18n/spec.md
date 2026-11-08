# 009 · Panel en español e inglés (i18n)

**Rama:** `009-i18n` · **Base:** `008-globo` · **Estado:** aprobada para implementar

Ampliación fuera del mínimo del enunciado. El panel sigue siendo en español por defecto (la constitución pide
español en documentación, commits y comentarios; no restringe el idioma de la interfaz).

## Requisitos

- **FR-001.** Selector de idioma «ES / EN» visible en la cabecera, con `aria-pressed` y nombre accesible
  («Idioma» / «Language»). Por defecto **español**; la elección se guarda en `localStorage` (`idioma`) y se
  recupera al volver.
- **FR-002.** El cambio es inmediato, sin recargar la página y sin volver a pedir datos a la API.
- **FR-003.** Se traduce **todo el texto propio del panel**: cabecera, estado del sistema, origen de datos,
  filtros y sus mensajes de validación, mapa (leyenda, ficha, resumen al pasar el ratón, avisos), globo,
  tabla, comparación histórica, recuentos, distribuciones, gráficos, vistas de datos, avisos de error y de
  datos desactualizados, textos `aria-*` y `title`.
- **FR-004.** Números y fechas siguen el idioma: en español coma decimal (`4,5`), en inglés punto (`4.5`).
  Los instantes siguen en **UTC** en ambos idiomas.
- **FR-005.** No se traducen los **datos**: nombres de país del catálogo, subregiones, `place` de USGS,
  identificadores, tipos de magnitud. Los valores de dominio que el panel muestra como etiqueta fija
  («Sin país asignado», «REPRODUCCIÓN», «SINTÉTICO») sí se traducen en la interfaz («No country assigned»,
  «REPLAY», «SYNTHETIC»), pero los filtros envían a la API exactamente los mismos parámetros.
- **FR-006.** `<html lang>` cambia a `es` o `en`.
- **FR-007.** Sin dependencias nuevas: diccionarios TypeScript tipados. Si al diccionario inglés le falta una
  clave del español, la compilación falla.

## Criterios de aceptación

- **AC-1.** Vitest: el diccionario inglés tiene las mismas claves y los mismos marcadores `{n}` que el español;
  ninguna traducción vacía.
- **AC-2.** Vitest: al cambiar a inglés cambian la cabecera y un bloque con datos, `lang` pasa a `en` y la
  elección se guarda; al recargar el servicio se recupera.
- **AC-3.** Los tests existentes (en español) siguen en verde sin cambiar sus textos esperados.
- **AC-4.** En el navegador, con datos reales, el panel completo se ve en inglés sin restos en español salvo
  los datos de FR-005 (captura en `evidencias/`).
