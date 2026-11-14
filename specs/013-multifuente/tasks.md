# Tareas 013

## Fase 0 — Spec y gobierno

- [x] T0 Constitución 3.0.0 (II, VIII; amplía I, III, IV) y regla de Cursor alineada
- [x] T1 spec.md, research.md (umbrales medidos), data-model.md, contracts/mensajes-kafka.md, plan.md, quickstart.md, checklist

## Fase 1 — Lógica pura (bloquea lo demás)

- [ ] T2 [P] `common/contrato.py`: v2 (validación, motivos nuevos, `fuentes` en `MensajeValido`, `construir_mensaje_v2` determinista) + `test_contrato_v2.py` (FR-003, FR-007)
- [ ] T3 [P] `fusion/normalizar.py` + fixtures reales USGS y EMSC + `test_normalizar.py` (FR-002, edge cases)
- [ ] T4 `fusion/emparejar.py` + `test_emparejar.py`: regla, réplicas, dos candidatos, id estable, principal, versión monótona, reentrega, determinismo (FR-004–FR-007)
- [ ] T5 [P] `producer/fuentes.py`: adaptadores USGS (lo de `feed.py`) y EMSC + `test_fuentes.py` (FR-001, FR-002)
- [ ] T6 [P] plan de intervalos del relleno (`relleno.planificar`) + `test_relleno.py` (FR-010)

## Fase 2 — Esquema

- [ ] T7 `db/init/006_multifuente.sql` + DDL equivalente en `producer/ciclo.asegurar_tablas`, `consumer/persistencia._DDL` y `fusion/estado.asegurar_fusion` (siembra FR-009)

## Fase 3 — Productores (US1)

- [ ] T8 `ciclo.una_pasada` y `app.py` genéricos por fuente; `config.py` (`FUENTE`, `TOPIC_FUENTE`, `EMSC_URL_BASE`); publicadas por fuente e ids de la respuesta
- [ ] T9 Compose: `producer` (usgs → `eventos.usgs`) y `producer-emsc`; `.env.example`

## Fase 4 — Fusión con Spark (US2)

- [ ] T10 `fusion/estado.py`, `fusion/job.py`, `fusion/salud.py`, `fusion/__main__.py`
- [ ] T11 `backend/Dockerfile.fusion`, `requirements-fusion.txt`; servicio `fusion` en Compose con volumen de *checkpoint* y healthcheck

## Fase 5 — Consumidor, API y panel (US2)

- [ ] T12 Consumidor: `fuentes` en historial y estado actual; `rellenar_estado` (FR-011)
- [ ] T13 API: `fuentes` en `/eventos` y `/eventos/mapa`; `ingesta_por_fuente` en `/status`; `docs/CONTRATO-API.md`
- [ ] T14 Panel: modelo, ficha, tabla, cabecera y atribución

## Fase 6 — Relleno (US3)

- [ ] T15 `observatorio/relleno.py` (descarga, original, publicación, marca) y orden `docker compose run --rm producer python -m observatorio.relleno …`

## Fase 7 — Verificación y documentación

- [ ] T16 Pila real: Europa con eventos (SC-001), fusión medida (SC-002, SC-003), corte de la fusión a mitad de lote (SC-004), relleno completo sin truncar (SC-005); evidencias
- [ ] T17 Verificador independiente (subagente) sobre spec, plan, tareas y evidencias
- [ ] T18 README, `docs/FUENTES-Y-LICENCIAS.md`, `docs/MEMORIA.md` (limitación de la comparación) y quickstart
