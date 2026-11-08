# Feature 005: API de consulta analítica

**Rama**: `005-api` | **Depende de**: 001 (`/health`, `/status`), 003 (estado actual y país) y 004 (histórico 2025)

La API ofrece al panel (feature 006) consultas de solo lectura sobre el estado actual,
con los mismos filtros en todas. Rutas, tablas e índices los fija el `plan.md`.

> **Enmienda (feature 007-memoria, contrato 0.3.0, aditiva)**: la API admite el parámetro `modo`
> (`live` por defecto | `replay`) en `/eventos`, `/eventos/mapa`, `/recuentos/*` y
> `/distribuciones/*`, y lo declara en las respuestas. Con `modo=replay` lee el estado actual de la
> reproducción (`replay.evento_actual`) y expone `reproducido_en`; `/comparacion-historica` solo
> acepta `live` (`replay` es 400). `/status` añade `eventos_replay`. Esto sustituye lo que dicen esta
> spec («Nada lee `replay.*`», «la 005 no expone replay») y el contrato 0.2.0 (FR-019 de 007). Los campos de
> 0.2.0 no cambian. Detalle en `docs/CONTRATO-API.md` y `specs/007-memoria/plan.md`.

## Requisitos

- **FR-001** (Enunciado §8): lista de eventos paginada, ordenada por `ocurrencia`
  descendente y `event_id` como desempate. Cada fila: `event_id`, `ocurrencia`, `updated`,
  `magnitud`, `profundidad`, `longitud`, `latitud`, país (código y nombre), subregión y
  `sintetico`. Incluye el total filtrado. Es la tabla alternativa al mapa.
- **FR-002** (Enunciado §8): consulta para el mapa con los mismos filtros, sin paginar y
  solo con los campos del círculo y su ficha. Tiene tope; si lo supera, devuelve
  `truncado=true` y el total real, nunca un corte silencioso.
- **FR-003** (Enunciado §8, §4.3): recuentos por país y por subregión. «Sin país
  asignado» es una categoría más, también en subregión (no tiene subregión).
- **FR-004** (Enunciado §8): recuentos por ventana fija de una hora UTC según
  `ocurrencia`, con las horas de cero eventos incluidas.
- **FR-005** (Enunciado §8, §6): distribuciones de magnitud y de profundidad con
  intervalos fijos que cubren valores negativos, y el recuento «sin valor» aparte. Un nulo
  no se cuenta como 0 ni cae en un intervalo.
- **FR-006** (Enunciado §8, §4.2): comparación histórica: eventos de las últimas 24 h con
  magnitud ≥ 4 frente a la media diaria de 2025 con los mismos filtros de magnitud y
  país/subregión. Denominador: 365 días, incluidos los de cero. Devuelve ambos recuentos,
  la media, el cociente, los filtros efectivos y el aviso de que el último periodo puede
  estar incompleto por retrasos y revisiones.
- **FR-007** (Enunciado §8, §9): `/status` añade, sin quitar campos de la 0.1.0: última
  ingesta correcta de USGS (última consulta al feed con HTTP 200 y sin error), periodo
  consultado (primera y última `ocurrencia` de eventos reales) y `datos_desactualizados`
  (`true` si no hay ingesta correcta o supera un umbral configurable). Sin base: `null`.
- **FR-008** (Enunciado §8): filtros comunes a FR-001 a FR-006: `desde`/`hasta` (UTC,
  sobre `ocurrencia`; `desde` inclusivo, `hasta` exclusivo), magnitud mínima y máxima,
  país (`ADM0_A3` o «Sin país asignado») y subregión. Valor mal formado: 400 sin detalles
  internos.
- **FR-009** (Enunciado §8, §11; Constitución VI): por defecto solo eventos reales; los
  sintéticos entran con un parámetro explícito y van marcados. Nada lee `replay.*`.
  FR-006 ignora ese parámetro.
- **FR-010** (Enunciado §8, §7): toda cifra sale de agregar el estado actual (una fila por
  evento), nunca de contar mensajes ni de contadores guardados.
- **FR-011** (Enunciado §9): CORS autoriza solo el origen exacto de Netlify (variable de
  entorno, sin valor por defecto) y `http://localhost:4200`; atiende `OPTIONS` y permite
  `ngrok-skip-browser-warning`. Sin comodín ni credenciales. Solo `GET` y `OPTIONS`
  (otros: 405). Sin rutas de administración ni `/docs`, `/redoc`, `/openapi.json`.
- **FR-012** (Enunciado §4.2, §7; Constitución IV): el denominador de 2025 sale de los
  18.302 eventos de `data/historico/2025/eventos.geojson`, cargados en un almacén propio
  consultable con SQL y con país por geometría. No se mezcla con `live.*` ni con el feed.
  `replay.evento_actual` no sirve (solo ~40 eventos). La carga es tarea de esta feature;
  su esquema lo decide el `plan.md`.
- **FR-013** (Enunciado §9; Constitución II): `docs/CONTRATO-API.md` y el OpenAPI pasan a
  0.2.0 (cambio aditivo) antes de que el panel use los campos. Instantes en UTC con
  milisegundos.
- **FR-014** (Enunciado §9): sin PostgreSQL, los endpoints analíticos dan 503 con cuerpo
  genérico, nunca listas vacías ni ceros; `/status` sigue en 200.

## Decisiones

- **Decisión**: la comparación usa magnitud mínima efectiva = máx(4, pedida) y declara el
  filtro efectivo. La fecha no aplica: la ventana es fija (24 h hasta `generated_at`).
- **Decisión**: con filtro de magnitud, los eventos de magnitud nula quedan fuera; sin él,
  entran.
- **Decisión**: sin `desde`/`hasta`, los recuentos por hora usan las últimas 24 h; máximo
  31 días (400 si se excede). País y subregión a la vez se combinan con Y.
- **Decisión**: paginación `limite`/`desplazamiento` (defecto 100, máximo 500).
- **Decisión**: el «último acceso correcto a la API» lo mide el panel; el etiquetado
  «REPRODUCCIÓN» queda para la 006, la 005 no expone replay.

## Rendimiento (Enunciado §10)

Con ~20.000 eventos deben responder rápido (≤ 1 s en local): `/health`, `/status`, lista,
mapa, recuentos por país/subregión/hora y distribuciones. Pueden ser más lentas (≤ 3 s) la
comparación histórica (agrega 18.302 filas de 2025) y el mapa sin filtros cerca del tope.
Se mide con tres tamaños; lo replicado se marca como sintético. El panel refresca cada 60 s.

## Criterios de aceptación

- **AC-1** (§11, nuevo y reenvío): insertar un evento real lo hace aparecer una vez en
  lista, mapa y recuentos; reenviar la misma versión no cambia ninguna respuesta.
- **AC-2** (§11, revisión): una versión posterior que cambia país o magnitud actualiza la
  lista y mueve los recuentos (el país antiguo baja); una versión antigua llegada después
  no cambia nada.
- **AC-3** (§11, nulo): con `magnitud: null`, el evento sale con `null` y suma en «sin valor».
- **AC-4** (§11, marítimo): un evento sin polígono sale como «Sin país asignado» en
  recuentos por país y subregión y se encuentra filtrando por ese valor.
- **AC-5** (§8, horas): en un rango de 6 h con eventos en 3, hay 6 ventanas y 3 con 0.
  10:59:59.999Z y 11:00:00.000Z caen en ventanas distintas.
- **AC-6** (§8, comparación): sin más filtros, la media 2025 es 18.302 / 365 ≈ 50,14.
  Con un país sin eventos en 2025 la media es 0, no se omite, y el aviso va siempre.
- **AC-7** (§8, coherencia): con los mismos filtros, el total de la lista, el del mapa y la
  suma de recuentos por país coinciden.
- **AC-8** (§11, replay/sintéticos): tras una reproducción las cifras no cambian; un
  sintético solo aparece con el parámetro explícito.
- **AC-9** (§9, CORS): `OPTIONS` con `Origin` de Netlify y con `http://localhost:4200`
  devuelve 2xx con ese origen exacto y `ngrok-skip-browser-warning` permitida; otro
  origen no recibe cabeceras CORS; `POST` da 405; `/docs` da 404.
- **AC-10** (§8, `/status`): con la última consulta correcta dentro del umbral,
  `datos_desactualizados=false`; fuera del umbral o sin ninguna, `true`.
- **AC-11** (§9, fallo): con PostgreSQL parado, un endpoint analítico da 503 y `/status`
  da 200 con `null`.

## Fuera de alcance

Panel Angular, Netlify y ngrok (006), memoria (007), autenticación, rutas de
administración, escritura y consulta de replay.

## Hecho cuando

AC-1 a AC-11 pasan con tests y evidencias en `specs/005-api/evidencias/`, el contrato está
en 0.2.0 y la pila arranca con `docker compose up --build -d`.
