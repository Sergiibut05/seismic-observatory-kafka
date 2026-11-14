# Verificación independiente de 013-multifuente

Verificador (subagente), 2026-11-14, rama `013-multifuente` (commit 211131c). Pila real ya levantada; no se paró nada, no se lanzó el relleno, no se hicieron commits.
Ficheros generados por la verificación: `pytest-backend.txt`, `ngtest-frontend.txt`, `verificacion-salida-verificador.txt`, `consultas-extra-verificador.txt`, `git-grep-secretos.txt`.

## Tabla de criterios

| Criterio | Veredicto | Por qué |
|---|---|---|
| Pila: 7 servicios healthy | PASA | `docker compose ps`: api, consumer, fusion, kafka, postgres, producer, producer-emsc, todos `(healthy)`. |
| Tests backend | PASA | `docker compose run --rm --no-deps consumer pytest -q` -> `856 passed in 4.08s` (`pytest-backend.txt`). |
| Tests panel | PASA | `npx ng test --watch=false` -> 37 ficheros, 394 tests pasan (`ngtest-frontend.txt`). `ng build` no se ejecutó. |
| SC-001 Europa en 24 h | PASA | SQL §7: 107 eventos `{emsc}`, 0 de USGS. La API (`/eventos/mapa?desde=ayer`, 432 eventos, filtrados por la caja en cliente) da los mismos 107. |
| SC-002 >= 95 % fusionados (M >= 4) | PASA | SQL §5: M >= 4: 28.728 de 28.917 pares en regla en el mismo evento = 99,3 % (M < 4: 99,1 %). |
| SC-003 sin duplicados ni pares sin fusionar | PASA | §3 es tautológica (PK sobre `event_id`). Lo que importa: §6, 341 pares sin fusionar y los 341 explicados por el caso «dos candidatos»; consulta extra A: 0 eventos fusionados con miembros fuera de regla (>30 s o >100 km). |
| SC-004 corte de la fusión a mitad de lote | NO VERIFICABLE (estado final PASA) | Ver F1: la evidencia no prueba que el corte fuera a mitad de lote ni que hubo reentrega. Consistencia final correcta: §1 publicadas = en fusión (emsc 171.499/171.499; usgs 55.560/55.560); §2 181.476 canónicos, 0 faltan, 0 con versión distinta; 225.357 versiones con 225.357 posiciones (topic, partición, offset) distintas. |
| SC-005 relleno sin consultas truncadas | PASA | `ingesta.consultas` del relleno: suma de `features` = recuento previo (EMSC 171.548 = 171.149 + 222 + 177; USGS 54.450 = 54.242 + 208); máximo por consulta 7.817 (EMSC, tope 8.000; corte real ~10.000) y 4.159 (USGS). |
| FR-001 un productor y un topic por fuente | PASA | `kafka-topics.sh`: `eventos.usgs`, `eventos.emsc`, `eventos.live`, `eventos.replay`, 3 particiones, retención 604800000. |
| FR-002 EMSC FDSN, `ke`, `lastupdate` | PASA | `fuentes.py`; 177 exclusiones EMSC con motivo en el relleno; tests. |
| FR-003/005/006/007 fusión v2, id canónico, principal, versión | PASA | Mensaje real de `eventos.live` leído con `kafka-console-consumer`: clave `emsc-20260628_0000184` = `event.id`, `schema_version` 2, `fuentes[]` con `principal`, profundidad 176,8 positiva. Eventos con 2 informes: 45.541 con id USGS y 42 con id `emsc-` (EMSC llegó antes), coherente con FR-005. |
| FR-004 regla 30 s / 100 km, nunca misma fuente | PASA | Extra A (0 fuera de regla); PK `(fuente, id_origen)` y `emparejar.py`. |
| FR-008 Kafka antes del commit, sin pérdida | PASA (parcial) | `job.py`: escritura en Kafka y luego `COMMIT`. Sin pérdida demostrada (§1, §2). La reentrega no se observó (0 `result=omitido` en el consumidor). |
| FR-009 siembra de eventos previos | NO VERIFICABLE | El log tras el corte dice `sembrados=0`; no hay caso real. Solo tests unitarios. |
| FR-010 relleno por tramos, marca, idempotente | PASA (parcial) | Tramos y recuentos correctos. «Repetirlo no republica» no se ejercitó (no se debía relanzar); los `omitidos` 208/222 del último tramo vienen del solapamiento con el directo. |
| FR-011 fuentes en consumidor, API y panel | PASA | `/eventos` y `/eventos/mapa` devuelven `fuentes`; 0 filas con `fuentes='{}'`; panel: tests de `mapa-ficha`, `puro/fuentes` y cabecera «Eventos reales de USGS y EMSC». |
| FR-012 replay, humo, sintéticos | PASA (por tests) | Suite verde; `/status` con `eventos_replay=40`. No se relanzó la prueba de humo. |
| FR-013 comparación solo USGS | PASA | `/comparacion-historica`: ventana 27 eventos M >= 4, base 18.302, aviso «Solo cuenta lo que publica USGS». SQL: 26 de 40 M >= 4 de 24 h tienen `usgs` (la API midió 27 unos minutos antes; la ventana se desplaza). Unión 2025 M >= 4 = 21.938 (coincide con la spec). |
| `/status` `ingesta_por_fuente` | PASA | `{"emsc": "...12:07:08Z", "usgs": "...12:07:01Z"}`. |
| Secretos en Git | PASA | `git grep -i -E "authtoken|password="`: 68 líneas, todas nombres de variable, tests con contraseñas ficticias y documentación; `POSTGRES_PASSWORD=` vacío en `.env.example`; `.env` no versionado. Variables nuevas presentes en `.env.example`. |
| Coherencia documental (Modo 1) | PASA con reservas | Todos los FR/SC se cubren por alguna tarea (FR-012 y FR-013 sin tarea propia, F5); constitución 3.0.0 coherente con compose y código. Incoherencias menores abajo. |

## Fallos e incoherencias

**F1 (media) `resiliencia-fusion.txt` no demuestra el corte a mitad de lote.** El último lote registrado antes del SIGKILL (lote 7) acabó a las 11:42:02 y el corte fue a las 11:42:10, con disparo cada 15 s: lo probable es que cayera entre lotes (el lote 8 habría empezado hacia :17). Tras reiniciar, el lote 8 aparece con `nuevos=4996 sin_cambios=0`, sin rastro de reentrega; no hay recuentos antes/después ni mensajes duplicados en Kafka; el consumidor no registró ningún `result=omitido`, así que la ventana crítica (Kafka escrito, estado sin confirmar) no se ejercitó. La consistencia final sí es correcta. Recomendación: repetir con un corte dentro del lote y registrar recuentos antes y después. No lo hice porque se pidió no parar la fusión.

**F2 (baja) Contenedores con imagen distinta de la etiqueta.** `observatorio-backend:local` es `sha256:7411...` (creada 12:05:49, la usa `api`), pero `consumer`, `producer` y `producer-emsc` corren `sha256:08a82...` (arrancados 11:37). Los tests se ejecutaron con la imagen nueva. Reproducir: `docker inspect --format '{{.Image}}' seismic-observatory-consumer-1 seismic-observatory-api-1`.

**F3 (baja) `quickstart.md` desfasado.** Paso 3 dice `result=lote`; el log real es `result=listo component=fusion action=lote`. Paso 5: relleno «del orden de una hora»; publicar tardó 121 s y el consumidor ~45 min (~75 eventos/s).

**F4 (baja) cifras de `research.md` y `spec.md`.** «Unos 200.000 informes» y EMSC 2026 «unos 65.000»; lo real: 225.998 (54.450 + 171.548) y ~92.000 de EMSC en 2026. Se cita 18.305 (USGS M >= 4 de 2025) en una sección y 18.302 en otra. El párrafo «coinciden en un 97 %» queda matizado por la medición posterior (+20 %), explicada más abajo.

**F5 (baja) trazabilidad en `tasks.md`.** FR-012 y FR-013 sin tarea propia. T16 y T17 sin marcar (esperado hasta cerrar esto). `spec.md` sigue en «Borrador».

**F6 (baja) `failOnDataLoss=false` en `job.py`.** Si la fusión estuviera parada más que la retención (7 días), Spark seguiría sin avisar y perdería mensajes, contra «nunca una pérdida» (FR-008, principio III). No está documentado como límite.

**F7 (baja) SC-001 no ejecutable literalmente con la API.** La spec propone contar en la API dentro de la caja de Europa, pero no hay filtro por caja (`lat_min` da `parametro_invalido`); se verificó filtrando `/eventos/mapa` en cliente y con SQL. Además `verificacion.sql` §3 no puede fallar por construcción.

**F8 (baja, observación)** `ultima_ingesta_correcta` es global (`SQL_ULTIMA_INGESTA`): si cae USGS y EMSC sigue bien, `datos_desactualizados` no se activa; solo se vería en `ingesta_por_fuente`. FR-006 dice «EMSC dentro de la caja»; el código usa EMSC si cualquier informe del evento cae en la caja.

## No verificado

- Corte de la fusión dentro de un lote y reentrega idéntica descartada por el consumidor.
- Siembra FR-009 con eventos previos reales.
- Idempotencia del relleno al relanzarlo (prohibido relanzar).
- `ng build`, prueba de humo y replay con la pila (solo tests unitarios).
- Panel en navegador (solo tests de Vitest).
- EMSC caído (US1 escenario 2): solo tests unitarios.

---

## Seguimiento de los hallazgos (tras el informe del verificador)

| Hallazgo | Qué se hizo | Evidencia |
| --- | --- | --- |
| F1 corte no demostrado | Repetido con la fusión bloqueada a propósito justo después de escribir en Kafka (`LOCK TABLE fusion.informe IN EXCLUSIVE MODE` desde otra sesión) y SIGKILL en esa ventana. El lote 68 se repitió idéntico y el consumidor lo descartó (`result=omitido reason=duplicado`). **SC-004: PASA** | `resiliencia-fusion.txt` (el intento anterior queda como `resiliencia-fusion-intento1.txt`) |
| F2 imágenes distintas | `docker compose up -d`: productores, consumidor y API con la misma imagen | — |
| F3 quickstart | `result=listo action=lote`; tiempos medidos del relleno (publicar ~2 min, fusión ~10 min, consumidor ~45 min) | `quickstart.md` |
| F4 cifras | 227.055 informes; EMSC 2026 ≈ 92.000; 18.305 (`/count` el 14-nov) frente a 18.302 (base del 2-nov) explicado | `research.md`, `spec.md` |
| F5 tareas | T17 marcada; T19 (FR-013), T20 (FR-012/FR-010), T21 (SC-004) añadidas; spec en «Implementada» | `tasks.md`, `spec.md` |
| F6 `failOnDataLoss` | Documentado como límite (parada de la fusión de más de 7 días) | `research.md`, «Límites de la garantía» |
| F7 SC-001 por API | Sin filtro por caja en la API: se mide con SQL (sección 7 de `verificacion.sql`) y, en cliente, con `/eventos/mapa` | `verificacion.txt` |
| F8 principal y frescura | FR-006 redactado como hace el código (algún informe en la caja); frescura global documentada como límite | `spec.md`, `research.md` |
| FR-009 siembra no verificable | 1.376 eventos previos sembrados con su id; 279 recibieron su pareja EMSC; 0 movidos a otro id; 0 duplicados | `siembra.txt` |
| FR-012 / FR-010 sin ejercitar | Prueba de humo persistida; reproducción con 40 eventos; relleno repetido sobre noviembre: 0 publicados, 3.649 omitidos | `pila-humo-replay-relleno.txt` |
