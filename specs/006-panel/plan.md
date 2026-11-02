# Plan 006 (compacto)

El panel es una SPA de solo lectura en `frontend/` que consume **únicamente** la API 0.2.0
(`docs/CONTRATO-API.md`, sin tocarla) y se publica en Netlify. No añade servicios, tablas ni
cambios de contrato. Todo el texto de la interfaz, los logs de consola y los comentarios van en
español. No hay `research.md` aparte: las decisiones viven aquí.

## Decisiones

1. **Angular 21.2.x, standalone + signals + zoneless.** Angular 22 (`latest`, CLI 22.2.5) exige
   Node `^22.22.3`; el entorno tiene **22.14.0**. La última mayor compatible es la **21 LTS**
   (CLI 21.2.29, `@angular/build` 21.2.29, `@angular/core` 21.2.25; todos piden Node
   `^20.19 || ^22.12 || >=24`). Se crea con `npx @angular/cli@21.2.29 new` y se **fijan las
   versiones exactas** que resuelva (sin `^` ni `~`; `.npmrc` con `save-exact=true`, `package-lock.json`
   versionado, `npm ci` como único modo de instalar; un test falla si aparece `^`/`~`). Se revisa al
   subir Node a ≥ 22.22.3. Sin `NgModule`, sin `zone.js` (predeterminado en 21), `provideHttpClient(withInterceptors([...]))`,
   `provideRouter` con una sola ruta `''` (+ `**` → `''`; el panel es una pantalla; la redirección SPA de Netlify cubre
   recargas). Fuentes del sistema, sin CDN (sin peso, sin terceros, sin CSP extra).
   - `src/app/modelos/api.ts`: tipos del contrato (solo campos documentados; `null` explícito).
   - `src/app/nucleo/`: `config.service` (lee `config.json` con `provideAppInitializer`; valida HTTPS, o `http` solo
     `localhost`/`127.0.0.1`; sin barra final), `api.service` (un método por endpoint, solo `GET`), `cabeceras.interceptor`
     (añade `ngrok-skip-browser-warning: true` y **rechaza** cualquier método ≠ `GET`: así AC-8 se prueba en un sitio),
     `filtros.store` (signals: filtros editados y filtros aplicados), `panel-datos.service` (un signal por bloque
     `{estado: cargando|ok|error, datos, lecturaOk, error}`), `refresco.service` (temporizador 60 s,
     `visibilitychange`).
   - `src/app/puro/` (TypeScript sin Angular, cada uno con su `.spec.ts`): `filtros.ts` (validar, a query string, ventana
     de `/recuentos/hora`), `escalas.ts` (radio, color, leyenda), `desactualizado.ts`, `cola-refresco.ts`, `formato.ts`
     (`ND`, fechas UTC + hora local), `errores.ts` (clasifica 400/503/500/red/cuerpo no JSON).
   - `src/app/componentes/`: `estado/` (barra fija arriba), `filtros/`, `mapa/`, `tabla/`, `recuentos/`,
     `distribuciones/`, `comparacion/`, `grafico-barras/` (SVG, compartido), `nota-aviso/` (pie permanente).
   - Un cambio de filtros no consulta al instante: tras 400 ms sin cambios pasa de «editados» a «aplicados» y pide **una**
     ronda. Todos los componentes leen los aplicados: una sola fuente (FR-007).
2. **Gráficos: SVG propio (`grafico-barras`), sin librería.** Todo es barra (país, subregión, hora, magnitud,
   profundidad) y las 3 vistas necesarias caben en un componente de ~80 líneas con `role="img"`, título/descripción y una
   `<table>` equivalente dentro de `<details>` (FR-015). Chart.js/ngx-charts añaden 60–200 kB y un modelo de
   accesibilidad que habría que sortear; con SVG controlamos el `sin_valor` aparte y las horas con cero (marca visible,
   no hueco). Si un día hace falta otro tipo de gráfico se reabre. **Leaflet 1.9.4 + `@types/leaflet` 1.9.22** (exactos; la 2.0 sigue
   en alfa). `preferCanvas: true` con `L.circleMarker` para 5.000 puntos. **Mapa base**: teselas OSM
   `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, `maxZoom 19`, atribución obligatoria «© colaboradores de OpenStreetMap»
   con enlace a `openstreetmap.org/copyright`, visible siempre. No necesita clave ni cuenta; sí cumplir la política de uso
   (uso razonable, sin descargas masivas, sin precarga, `Referer` normal del navegador): un panel con zoom manual y una capa de
   fronteras queda muy por debajo. Si el tráfico creciera, cambiar de proveedor es cambiar una constante.
   Con el mapa en canvas los círculos no son enfocables: la **tabla es la alternativa por teclado**, con un botón «Ver en el
   mapa» por fila que selecciona el evento y abre la ficha (id, ocurrencia, `updated`, magnitud, profundidad, país).
3. **Catálogo: `frontend/scripts/catalogo.mjs` (Node, no PowerShell).** Mismo comando en Windows, Netlify y
   cualquier CI, y no añade un segundo script que mantener. `npm run catalogo:copiar` copia
   `../catalogo/paises.geojson` a `public/datos/paises.geojson` (sobrescribe); `npm run catalogo:verificar` calcula el SHA-256 de la
   copia y lo compara con `output.sha256` de `catalogo/paises.manifest.json` (y con el origen si existe); se ejecuta
   en `prestart`, `prebuild` y `pretest`, y un `.spec.ts` lo repite. La copia **se versiona** (2,3 MB; así el build de
   Netlify no depende de `../catalogo`) y se marca `-text` en `.gitattributes` como el original (los bytes no cambian y el hash vale).
   Editarla a mano rompe el hash y el build; se restaura con `catalogo:copiar`. Cabecera del script y quickstart lo dicen.
4. **Configuración**: `public/config.json` versionado `{"apiBaseUrl": "http://127.0.0.1:8000"}` (solo esa clave);
   `public/config.ejemplo.json` con `https://SUBDOMINIO.ngrok-free.app` (marcador, no una URL real). Se edita **antes de
   compilar** (Constitución, spec): Angular lo copia tal cual a `dist/`, y se lee con `fetch(..., {cache: 'no-store'})` al
   arrancar. Valor inválido o fichero ausente → pantalla de error de configuración, no peticiones. Sin variantes por
   entorno ni secretos (FR-013). `netlify.toml` marca `/config.json` con `Cache-Control: no-cache`.
5. **Ejecución y pruebas.** Dev: `cd frontend; npm ci; npm start` (`ng serve`, `http://localhost:4200`, origen ya permitido por
   CORS) contra `http://127.0.0.1:8000` con `docker compose up -d`. `npm test` = `ng test --watch=false`
   con el runner de Angular 21 (**Vitest** + `jsdom`, sin navegador; el CLI los trae y se fijan exactos). Pruebas: lógica pura y servicios
   con `HttpTestingController` + `jsdom`; `grafico-barras` y tabla con `TestBed`. El mapa Leaflet no se prueba en `jsdom` (sin
   canvas/layout): su lógica de decisión (radio, color, ND) es pura y se verifica en navegador real. Verificación final con el navegador integrado
   `cursor-ide-browser` contra la API real, capturas en `specs/006-panel/evidencias/` (T11). Build: `npm run build`
   (`ng build`, producción) → `frontend/dist/panel/browser/`.
6. **Netlify**: `netlify.toml` en la **raíz** con `[build] base = "frontend"`, `command = "npm ci && npm run build"`,
   `publish = "dist/panel/browser"` (relativo a `base`; nombre del proyecto `panel`, se confirma con `ng build`),
   `NODE_VERSION = "22.14.0"` y `[[redirects]] from = "/*" to = "/index.html" status = 200`. Sin variables ni secretos. El quickstart
   cubre: `ngrok http 8000` en el anfitrión (el authtoken se configura con `ngrok config add-authtoken` en la máquina
   del alumno, nunca en el repo; `ngrok.yml` ya está en `.gitignore`), pegar la URL HTTPS en `config.json` **antes** de compilar,
   poner `CORS_ORIGEN_NETLIFY=https://<sitio>.netlify.app` en `.env` y `docker compose up -d api` para reiniciar la API, y probar
   con `curl.exe -i -X OPTIONS` el preflight. **Sin Dockerfile del frontend**: son cinco servicios y el panel va a Netlify;
   el desarrollo usa `ng serve` en el anfitrión (Constitución I y VIII).

## Comportamiento que no se ve en el contrato

- **Fechas**: los campos `datetime-local` se interpretan y rotulan en **UTC** (la API solo habla UTC) y se serializan con
  `toISOString()` (`…:00.000Z`; no hay `+`, así que no hace falta `%2B`). `URLSearchParams` codifica el resto. Vacío → no se envía.
  `desde ≥ hasta` o `mín > máx` → error junto al campo, **sin** llamar a la API. `incluir_sinteticos` no existe en el código.
- **Por endpoint**: mapa/tabla/recuentos/distribuciones: todos los filtros; `/recuentos/hora`: además se acota a 31 días
  (`acotarVentanaHora`: si el rango supera 31 días usa los últimos 31 hasta `hasta` o ahora, y el panel lo escribe); `/comparacion-historica`: solo magnitud y
  país/subregión (el formulario lo rotula y no envía fechas). Selector de país/subregión: «Sin país asignado» siempre presente;
  los demás valores salen de `/recuentos/pais` y `/recuentos/subregion` **sin filtros** (2 `GET` solo al arrancar, fuera de la ronda de 60 s), no de un listado inventado.
- **Ronda de refresco** = `/status` + mapa + tabla + país + subregión + hora + magnitud + profundidad + comparación (9 `GET`, ~45 ms
  c/u en la API). `cola-refresco.ts` garantiza: una ronda en curso no se repite; una petición nueva durante la ronda se anota **una** vez y
  se ejecuta al terminar; con la pestaña oculta el temporizador se cancela y al volver se lanza una ronda inmediata (si no se acaba de lanzar otra).
- **Errores y datos antiguos** (FR-011): cada bloque conserva `lecturaOk` y `datos` de su último 200. En error muestra «No se pudo
  actualizar (motivo)» y debajo los datos con «datos del 15:03:28 (13:03 UTC), desactualizados»; el siguiente refresco lo recupera solo. Un 200 con cuerpo no JSON (la página
  de aviso de ngrok) cuenta como error `respuesta_invalida`.
- **Estado del sistema** (FR-008): barra fija con último acceso correcto (hora de la última respuesta 200 de `/status` medida por el panel),
  `ultima_ingesta_correcta`, `periodo_consultado`, `eventos_reales`. Aviso destacado (`role="alert"` una vez; el resto `aria-live=polite`) si
  `datos_desactualizados=true`, `base_de_datos="fallida"`, o `/status` falla (API sin respuesta). `calcularEstado()` (puro) deriva los avisos; los `null` se pintan «ND».
- **Escalas** (en `escalas.ts`, fuente única de mapa y leyenda): radio `3 + 2,5·clamp(M, 0, 8)` px; magnitud `null` → radio fijo 5 px,
  gris con borde discontinuo y etiqueta «ND». Profundidad por los **mismos intervalos de la API** (`<0`, `0–10`, …, `≥700`) con una rampa secuencial apta
  para daltonismo (clara = somero, oscura = profundo; `<0` con color propio) y `null` gris «ND». Los números exactos se fijan en los tests.
- **Diseño** (skill `frontend-design`; el developer decide y justifica en 3 líneas en la tarea T4): sobrio de herramienta de observación,
  tinta oscura sobre fondo claro, un único acento, sin la receta crema + serif + terracota; tipografía del sistema con escala clara; contraste ≥ 4,5:1.

## Coste (§10)

| Operación | Estructura | Medio | Peor caso |
| --- | --- | --- | --- |
| Pintar el mapa | `L.circleMarker` en canvas, una pasada | O(n), n ≤ 5.000 | igual; sin tope serían 20 MB de JSON, por eso el tope de la API |
| Barras de recuentos / distribuciones | un `rect` por categoría | O(k), k ≤ 242 países | O(k); horas O(h), h ≤ 745 |
| Tabla | solo la página pedida | O(`limite`) ≤ 500 | igual |
| Ronda de refresco | 9 `GET` sin solapes | ~9 peticiones/min por pestaña | 9 + 1 diferida por cambio de filtros |

## Constitution Check

I cinco servicios intactos; el panel no está en Compose (Netlify; `ng serve` en dev). II consume solo campos del contrato 0.2.0 (tipos propios en `modelos/api.ts`).
III–VI el panel no escribe, no calcula agregaciones (usa las de la API, desde el estado actual), «Sin país asignado» es una opción y categoría, `incluir_sinteticos` jamás se envía, no pide replay.
VII solo `GET`, sin secretos en `config.json` ni en el bundle (búsqueda de `authtoken`/`NGROK_AUTHTOKEN` en T10), sin terceros salvo teselas OSM. VIII dependencias mínimas: Angular, Leaflet y sus tipos, y lo que trae el CLI para tests; sin gráficos, sin UI kit, sin estado externo (NgRx).

## Desviaciones y riesgos

- **Angular 21, no 22** (por Node 22.14.0). Riesgo bajo: la mayor 21 tiene soporte LTS.
- La copia de `paises.geojson` está en Git (duplica 2,3 MB) a cambio de un build de Netlify autocontenido; la integridad la garantiza el hash.
- Teselas OSM de un tercero: sin ellas el mapa sigue mostrando fronteras y círculos (la capa base es opcional en caso de fallo; la atribución se mantiene).
- El mapa no tiene prueba automática en `jsdom`; se cubre con navegador real (T11) y lógica pura probada.
- `.gitattributes` y `netlify.toml` están fuera de `specs/`: los toca el developer en T1 y T10.
- **Implementación T1–T4 (desviaciones mínimas)**:
  - **`vitest` 4.0.18, no 4.1.x**: con `npm` 10.9.2 `vitest@4.1.12` hace fallar `npm install` (`Cannot read properties of null (reading 'edgesOut')`, fallo del resolutor de pares). 4.0.18 es compatible con `@angular/build` 21.2.29 y resuelve limpio. Revisar al subir de `npm`/Node. Versiones exactas: `@angular/*` 21.2.25, `@angular/build`/`cli` 21.2.29, `jsdom` 28.1.0, `typescript` 5.9.3, `rxjs` 7.8.2, `tslib` 2.9.1, `prettier` 3.9.10.
  - **Cabecera `ngrok-skip-browser-warning: 1`** (el plan decía `true`): ngrok solo exige que la cabecera exista; la API la admite por CORS con cualquier valor.
  - **`src/node-minimo.d.ts`**: declara el mínimo de `node:fs`/`node:crypto`/`process` para `versiones.spec.ts` en lugar de añadir `@types/node` (Constitución VIII).
  - **Rutas**: `app.routes.ts` solo define `''` (sin componente) y `** → ''`; los componentes los coloca `app.html` en la rejilla, sin `<router-outlet>` (una sola pantalla).
  - **Paginación**: cambiar de página recarga solo el bloque tabla (1 `GET`), no la ronda de 9; un cambio de filtros sí lanza la ronda y vuelve a la página 0. Una petición nueva del mismo bloque cancela la anterior en vuelo.
  - **`ApiService`** rechaza como `respuesta_invalida` cualquier 200 cuyo cuerpo no sea un objeto JSON (la página de aviso de ngrok), además del error de parseo de `HttpClient`.
  - **Nombres**: las clases de componente no llevan sufijo (`Estado`, `Filtros`, `Mapa`, …; carpeta y fichero homónimos) y los tipos de filtros son `FiltrosEditados`/`FiltrosAplicados` para no chocar con el componente `Filtros`.
