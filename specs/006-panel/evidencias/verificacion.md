# Verificación T11 — navegador real (T19)

Fecha: 2026-11-08. URL: `http://localhost:4200`. API: `http://127.0.0.1:8000` (v0.3.0). Viewport ≥1280 px (1440×900).

| Criterio | Veredicto | Evidencia |
| --- | --- | --- |
| AC-3 mapa/tabla/recuentos mismo total | **PASA** (con ventana fija) | `02-filtros-aplicados.png`: total **204** en tabla, mapa «204 dibujados», recuentos «Total: 204» |
| AC-5 gráficos / ND | **PASA** | `05-nulo-nd.png` (sintéticos ON): fila `synthetic-caso-magnitud-nula`, magnitud **ND** |
| AC-6 comparación | **PASA** | `04-comparacion.png`; en análisis `analisis-2.png`: 21 / 50,1 / 0,42 |
| AC-7 estado sistema | **PASA** | `01-panel-completo.png`; `07-api-apagada.png` / `08-recuperada.png` |
| AC-8 solo GET | **PASA** (código + red) | `red.md`; interceptor en `cabeceras.interceptor.ts` |
| AC-10 accesibilidad | **PARCIAL** | No repetido en esta sesión; ver `accesibilidad.md` de T9 |
| AC-11 panel completo | **PASA** | Capturas `01`–`08` |
| AC-13 túnel API caída ≤60 s | **PASA con matiz** | `07-api-apagada.png`: alerta «La API no respondió»; **no** apareció sola tras `stop api` hasta forzar petición (**Aplicar** o **Restablecer**) → fallo UX para developer |
| AC-13 recuperación sin F5 | **PASA con matiz** | `08-recuperada.png`: **Restablecer** tras `start api` recuperó datos; varios **Aplicar** seguidos siguieron en error hasta Restablecer |
| AC-16 sintéticos apagados | **PASA** | Con interruptor apagado y solo reales: sin filas `synthetic-caso` en DOM; `10-sinteticos.png` con interruptor ON muestra aviso y leyenda **SINTÉTICO** (contorno discontinuo en mapa real) |
| AC-20 replay | **PASA** | `09-reproduccion.png` (en `specs/007-memoria/evidencias/`) |
| Suma países = total | **PASA** | Ventana 24 h: recuentos por país suman **204** (= total tabla/mapa en `02-filtros-aplicados.png`) |

## Fallos para el developer

1. Tras `docker compose stop api`, el panel **no** entra en error automáticamente en ≤60 s sin interacción (el refresco en segundo plano no bastó en la prueba).
2. Tras `docker compose start api`, **Aplicar** puede seguir fallando hasta **Restablecer** (estado de error atascado).
3. En una sesión posterior (~14:42 UTC), tras filtrar por ventana manual, el bloque «Eventos por país» mostró **Total: 480** mientras «Eventos por hora» y distribuciones mostraban **203/204** — posible desincronización de widgets (reproducir: aplicar `desde/hasta` y comparar totales).

## Revisión de los fallos (orquestador, 2026-11-08 14:44–14:52 UTC)

Repetido en el navegador de Cursor con la pestaña **visible** (`document.visibilityState === 'visible'`, comprobado por CDP):

1. **No era un fallo del panel.** Con la pestaña visible el refresco de 60 s funciona (2 GET a `/status` en 80 s). Tras `docker compose stop api` y 65 s sin tocar nada, la cabecera mostró «⛔ La API no responde: se muestran los últimos datos recibidos», con «Último acceso correcto a la API 14:44 UTC» y los bloques con sus datos anteriores marcados como desactualizados (`07b-api-apagada-automatico.png`). Tras `docker compose start api` y 65 s sin tocar nada, el panel volvió solo, sin avisos y con un acceso de las 14:47 UTC (`08b-recuperada-automatico.png`). En la sesión del verifier la pestaña estaba oculta, y el panel pausa el refresco con la pestaña oculta (FR-010), que es justo lo que se pide.
2. **Mejora aplicada.** «Aplicar» con los mismos filtros no hacía nada, porque no había cambio que lanzara la ronda. Ahora pide una ronda inmediata (`componentes/filtros/filtros.ts` y dos tests nuevos en `filtros.spec.ts`). Comprobado en vivo: de 1 a 2 GET a `/status` al pulsar «Aplicar».
3. **No era una desincronización.** Sin fechas en los filtros, país, subregión, mapa, tabla y distribuciones usan todo el periodo (480–481), mientras que `/recuentos/hora` usa su ventana de 24 h (202–204) (contrato de la API). El gráfico horario ahora lo dice: «Sin fechas en los filtros, este gráfico muestra las últimas 24 h; los demás bloques usan todo el periodo disponible.» Hay dos tests nuevos en `recuentos.spec.ts`. Con fechas aplicadas, los totales coinciden (`02-filtros-aplicados.png`: 204).

Vitest: 270 tests pasados (266 + 4).

## Comandos de arranque

`npm start -- --port 4200` falló en PowerShell (Angular tomó `4200` como nombre de proyecto). Se usó `npx ng serve --port 4200` en segundo plano.
