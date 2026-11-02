# Feature 006: Panel Angular + Leaflet

**Rama**: `006-panel` | **Depende de**: 005 (API 0.2.0, `docs/CONTRATO-API.md`) y el catálogo `catalogo/paises.geojson`

Panel web en `frontend/` que consume **solo nuestra API** (nunca USGS) y se publica en
Netlify. Toda la interfaz va en español. Librerías, estructura y estado los fija el `plan.md`.

## Requisitos

- **FR-001** (Enunciado §8, §3): mapa Leaflet con mapa base, fronteras y un círculo por
  evento (`/eventos/mapa`). Radio por magnitud, color por profundidad, leyenda de ambas
  escalas y ficha al seleccionar (id, ocurrencia, `updated`, magnitud, profundidad, país).
  Magnitud o profundidad `null` se dibujan con un estilo propio y la etiqueta «ND»
  (en leyenda y ficha), nunca como 0 ni como el círculo más pequeño sin marca.
- **FR-002** (Enunciado §8, §3): las fronteras salen de `frontend/public/datos/paises.geojson`,
  copia de `catalogo/paises.geojson` generada por un script del repo. Una única fuente de
  verdad: la copia no se edita a mano y el script la sobrescribe.
- **FR-003** (Enunciado §8): `/eventos/mapa` con `truncado=true` muestra un aviso con
  `devueltos` y el `total` real; nunca un corte silencioso.
- **FR-004** (Enunciado §8, §4.3): recuentos por país y por subregión (selector) con
  «Sin país asignado» como categoría más, y recuentos por ventana de una hora UTC con las
  horas de cero eventos visibles.
- **FR-005** (Enunciado §8, §6): distribuciones de magnitud y de profundidad con los
  intervalos de la API y el recuento `sin_valor` mostrado aparte y visible.
- **FR-006** (Enunciado §8, §4.2): comparación histórica: 24 h con M≥4 frente a la media
  diaria de 2025, con cociente, filtros efectivos y el `aviso` de periodo posiblemente
  incompleto siempre visible. Con `estado=no_cargado` o `null`, muestra «no disponible»,
  no 0.
- **FR-007** (Enunciado §8): filtros de fecha (`desde`/`hasta`), magnitud (mín./máx.) y
  país/subregión, con «Sin país asignado» como opción. Una sola fuente de filtros alimenta
  a la vez mapa, tabla y gráficos; la comparación solo usa magnitud y país/subregión y lo
  indica. Se serializan al formato del contrato (ISO con `Z`, `%2B` si hiciera falta).
  Valores incoherentes (`desde ≥ hasta`, mín > máx) se rechazan en el formulario sin
  llamar a la API. Sin sintéticos: el panel nunca envía `incluir_sinteticos=true`.
- **FR-008** (Enunciado §8, §9): estado del sistema siempre visible: último acceso correcto
  a la API (medido por el panel, hora local con UTC), última ingesta correcta de USGS,
  periodo consultado y eventos reales. Aviso destacado si `datos_desactualizados=true`,
  si `base_de_datos=fallida` o si la API no responde. Los `null` se muestran «ND».
- **FR-009** (Enunciado §8, §11): tabla de eventos paginada (`limite`/`desplazamiento`)
  con los mismos filtros, columnas del contrato, magnitud/profundidad `null` como «ND» y
  total filtrado. Es la alternativa accesible al mapa y al color.
- **FR-010** (Enunciado §9): refresco automático cada 60 s, que se pausa con la pestaña
  oculta y se reanuda (con una consulta inmediata) al volver. Sin solapar peticiones ni
  repetir las que ya están en curso; un cambio de filtros consulta una vez.
- **FR-011** (Enunciado §11, §9): carga y error visibles por bloque. Si la API falla
  (red, 4xx/5xx, 503), el panel muestra un error claro, **conserva e identifica la última
  lectura correcta** («datos del …, desactualizados») y se recupera solo en el siguiente
  refresco cuando la API vuelve.
- **FR-012** (Enunciado §9): todas las peticiones llevan `ngrok-skip-browser-warning`.
  La URL base sale de `public/config.json` (HTTPS de ngrok; `http://127.0.0.1:8000` o
  `localhost` solo en desarrollo). El panel usa siempre solo `GET`.
- **FR-013** (Enunciado §9): sin secretos: ni el authtoken de ngrok ni credenciales en
  `config.json`, en el código Angular ni en Git. Solo la URL pública de la API.
- **FR-014** (Enunciado §8): nota visible y permanente: las cifras no son una predicción de
  terremotos ni una evaluación de riesgo; la cobertura y el tipo de magnitud pueden variar.
- **FR-015** (Enunciado §8, §13): accesibilidad básica: contraste suficiente, foco visible
  y navegación por teclado, etiquetas y roles `aria`, información que no depende solo del
  color (tamaño, texto, tabla) y texto alternativo de cada gráfico y del mapa.
- **FR-016** (Enunciado §11): sin datos de reproducción: el panel no los pide ni los
  muestra (la API no los expone).
- **FR-017** (Enunciado §3, §12): `frontend/` con dependencias fijadas y archivo de
  bloqueo, sin `node_modules` en Git; guía de ejecución, ngrok y Netlify en el `quickstart.md`.

## Decisiones

- **Decisión**: gráficos con una librería ligera y sin dependencias pesadas (barras
  basta); la elige el architect en el `plan.md`. Prohibidos motores de BI o de mapas
  propios; Leaflet es el único motor cartográfico.
- **Decisión**: `config.json` se edita **antes de compilar** (§9) y se copia tal cual al
  build; se lee al arrancar, pero no hay variante por entorno en tiempo de ejecución.
- **Decisión**: desarrollo en `http://localhost:4200` (origen ya autorizado en CORS)
  contra `http://127.0.0.1:8000`. Despliegue: la API ya está publicada en `127.0.0.1:8000`;
  en el anfitrión se ejecuta `ngrok http 8000` y su URL HTTPS va a `config.json`.
- **Decisión**: «último acceso correcto a la API» = instante del último `/status` con 200
  recibido por el panel; el refresco consulta `/status` junto al resto de bloques.
- **Decisión**: el panel acota los filtros de fecha a 31 días para `/recuentos/hora`
  (límite de la API) y lo indica; el resto de gráficos usan el rango completo.
- **Decisión**: la comparación usa solo magnitud y país/subregión; no se le envían las fechas
  (la API devolvería 400).

## Criterios de aceptación

- **AC-1** (§9, construcción): `ng build` de producción termina sin errores y deja un
  `dist/` con `config.json`, `datos/paises.geojson` y sin referencias a USGS.
- **AC-2** (§8, lógica pura): tests unitarios que pasan sobre formato de filtros
  (ISO con `Z`, omitir vacíos, rechazar rangos incoherentes), escala de radio por
  magnitud, escala de color por profundidad (incluida negativa y `null`) y cálculo de
  «datos desactualizados» / «lectura antigua».
- **AC-3** (§8, coherencia): en el navegador, con los mismos filtros, el total de la tabla,
  el del mapa (`total`) y la suma de recuentos por país coinciden.
- **AC-4** (§11, nulo): un evento con magnitud `null` aparece como «ND» en tabla, ficha y
  leyenda; la distribución muestra su `sin_valor`.
- **AC-5** (§11, marítimo): un evento sin país aparece como «Sin país asignado» en
  recuentos y se encuentra filtrando por esa opción.
- **AC-6** (§8, comparación): se ve «M≥4 24 h», media 2025, cociente y el aviso; con el
  histórico `no_cargado` se ve «no disponible».
- **AC-7** (§11, túnel/API apagada): al parar la API, en ≤ 60 s el panel muestra el error,
  marca la última lectura y el aviso de API sin respuesta; al volver, se recupera solo.
- **AC-8** (§9, refresco): con la pestaña visible hay una ronda de peticiones cada 60 s;
  oculta no hay ninguna; al volver, una inmediata. Toda petición lleva
  `ngrok-skip-browser-warning` y es `GET`.
- **AC-9** (§9, secretos): `public/config.json` solo contiene la URL de la API; una búsqueda
  de `authtoken` o `NGROK_AUTHTOKEN` en `frontend/` y en lo rastreado por Git no da nada.
- **AC-10** (§8, accesibilidad): recorrido por teclado de filtros, tabla y paginación;
  foco visible; cada gráfico y el mapa tienen alternativa textual; nota de no predicción visible.
- **AC-11** (§11, navegador real): comprobación con navegador real contra la API local
  (`docker compose up`), con capturas en `specs/006-panel/evidencias/`: panel completo,
  filtros aplicados, tabla, comparación, nulo/ND y API apagada.

## Fuera de alcance

Autenticación, panel de calidad, modo replay en pantalla, despliegue real en Netlify (se
documenta el procedimiento y se deja el build listo; lo hace el alumno con su cuenta),
memoria y conclusiones (007), cambios en la API.

## Hecho cuando

AC-1 a AC-11 pasan con evidencias en `specs/006-panel/evidencias/`, `config.json` apunta a
una URL configurable sin secretos y el `quickstart.md` permite al alumno publicar en Netlify.
