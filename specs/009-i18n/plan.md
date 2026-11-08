# Plan 009 · i18n

## Decisión: diccionarios propios con señales, no `@angular/localize`

`@angular/localize` traduce en compilación: un build y una URL por idioma (`/es/`, `/en/`) y recarga al
cambiar. Para un panel de una página en Netlify, con cambio inmediato (FR-002) y sin dependencias (FR-007),
basta un servicio con una señal y dos diccionarios tipados. Coste: no hay extracción automática de cadenas ni
pluralización ICU; los plurales que hagan falta se resuelven con dos claves (`…uno` / `…otros`).

## Estructura

- `src/app/i18n/es.ts`: `export const ES = { 'cabecera.titulo': 'Observatorio de actividad sísmica', … } as const;`
  y `export type Clave = keyof typeof ES;`. Claves planas con prefijo de bloque (`filtros.`, `mapa.`, `globo.`,
  `tabla.`, `comparacion.`, `recuentos.`, `distribuciones.`, `grafico.`, `estado.`, `errores.`, `formato.`…).
- `src/app/i18n/en.ts`: `export const EN: Record<Clave, string> = { … }` (falta de clave = error de compilación).
- `src/app/i18n/traducir.ts` (puro): `type Idioma = 'es' | 'en'`, `type Traductor = (c: Clave, p?: Record<string,
  string | number>) => string`, `crearTraductor(idioma)` que sustituye `{nombre}`, `localeDe(idioma)`
  (`es-ES` / `en-GB`) y `T_ES = crearTraductor('es')`.
- `src/app/i18n/i18n.service.ts`: `providedIn: 'root'`; `idioma = signal<Idioma>` (lee `localStorage.idioma`,
  por defecto `'es'`); `t = computed(() => crearTraductor(idioma()))`; `effect` que escribe `localStorage` y
  `document.documentElement.lang`. Plantillas: `{{ i18n.t()('mapa.titulo') }}` o un método `t(clave)` del
  componente que lea la señal (zoneless: la lectura de la señal en la plantilla basta para repintar).
- Funciones puras que generan texto (`puro/formato.ts`, `errores.ts`, `texto-comparacion.ts`, `filtros.ts`,
  `escalas.ts`, `barras.ts`, `globo.ts`, `desactualizado.ts`, `etiqueta-antiguos.ts`, `componentes/mapa/mapa-ficha.ts`):
  reciben un parámetro opcional `t: Traductor = T_ES` (y `idioma` para números) al final de la firma. Así los
  tests existentes no cambian (AC-3).
- Leaflet y globe.gl: la ficha, el resumen y la etiqueta se generan con el traductor vigente; al cambiar de
  idioma, un `effect` vuelve a pintar los marcadores con los datos que ya hay (sin pedir a la API, FR-002).
- Selector en `app.html` (cabecera), mismo estilo de botones segmentados que «Plano / Globo 3D».

## Riesgos

- Cadenas olvidadas: AC-4 lo comprueba en navegador y se buscan con `rg "[áéíóúñ¿¡]" src/app --glob '!*.spec.ts' --glob '!i18n/**'`.
- El orden de los parámetros nuevos no debe romper llamadas existentes: siempre opcionales y al final.
