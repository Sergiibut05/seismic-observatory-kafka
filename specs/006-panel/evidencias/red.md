# Red — panel local contra API (`T11` / `T19`)

Fecha: 2026-11-08. Origen: `http://localhost:4200` → `http://127.0.0.1:8000` (`frontend/public/config.json`).

## Rondas de peticiones (Performance API)

Tras varias acciones (carga inicial, **Aplicar**, **Restablecer**, cambio de magnitud), `performance.getEntriesByType('resource')` filtrado por `127.0.0.1:8000` muestra **9 rutas GET por ronda** (última ronda observada ~14:42 UTC):

| Ruta | `initiatorType` típico |
| --- | --- |
| `/status` | `xmlhttprequest` |
| `/eventos` | `xmlhttprequest` |
| `/eventos/mapa` | `xmlhttprequest` |
| `/recuentos/pais` | `xmlhttprequest` |
| `/recuentos/subregion` | `xmlhttprequest` |
| `/recuentos/hora` | `xmlhttprequest` |
| `/distribuciones/magnitud` | `xmlhttprequest` |
| `/distribuciones/profundidad` | `xmlhttprequest` |
| `/comparacion-historica` | `xmlhttprequest` (solo en modo **En directo**) |

En modo **REPRODUCCIÓN** no aparece `/comparacion-historica` (comprobado en sesión T19 con captura `09-reproduccion.png`).

**Conteo de rondas:** no se instrumentó un contador propio; con el refresco automático del panel hubo **varias decenas** de entradas en `performance` (3+ rondas completas visibles en la extracción CDP).

## Cabeceras

- El interceptor Angular (`frontend/src/app/nucleo/cabeceras.interceptor.ts`) añade en **cada GET** la cabecera `ngrok-skip-browser-warning: 1` y rechaza métodos distintos de GET.
- **No comprobado en cabeceras reales de red:** `PerformanceResourceTiming` en el navegador integrado de Cursor no expone los request headers; no se usó proxy ni DevTools Network con captura HAR. La evidencia del código es coherente con AC-9 del panel (solo GET + cabecera ngrok).

## Pestaña oculta = 0 rondas

**No comprobado.** El MCP `cursor-ide-browser` no permite poner la pestaña en estado `document.hidden` de forma fiable ni observar el `RefrescoService` con la pestaña en segundo plano sin automatización adicional fuera del alcance de esta sesión. Comportamiento esperado según diseño: el refresco periódico debería pausarse con pestaña oculta (documentar en T21 si el código lo implementa).
