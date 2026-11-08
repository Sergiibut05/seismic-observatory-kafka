# Análisis cross-artifact 007-memoria (T0)

**Alcance**: `spec.md`, `plan.md`, `tasks.md` vs `docs/ENUNCIADO.md` §10–§13 y `.specify/memory/constitution.md`.  
**Solo hallazgos CRÍTICOS / ALTOS** que bloquean implementar con confianza.

| ID | Severidad | Resumen | Corrección propuesta |
|----|-----------|---------|----------------------|
| I1 | **ALTA** | **Constitución (flujo de trabajo) + FR-013**: la spec exige enmendar `specs/006-panel/spec.md` (FR-007) **antes** de tocar código del panel; en `tasks.md` la enmienda es **T11**, que depende de **T10** (UI ya implementada en T7–T10). | Dividir T11: tarea **al inicio del bloque B** (solo `specs/006-panel/spec.md` + nota) **antes de T7**, o ejecutar esa enmienda como prerequisito de B. Dejar T11 actual como comprobación (`npm test` / build) tras T10 si hace falta. |
| I2 | **ALTA** | **Incoherencia spec ↔ tasks (cierre)**: en spec, «Hecho cuando» y varios párrafos citan **AC-1…AC-18**, pero la misma spec define **AC-19** (API `modo`) y **AC-20** (panel REPRODUCCIÓN) y `tasks.md` (T18, T19, T24) los trata como obligatorios para cerrar 007. | Actualizar `spec.md` («Hecho cuando», FR-001/FR-011 si aplica) para incluir **AC-19 y AC-20** y alinear la tabla de aceptación de la memoria (T17/T21) con esos dos criterios desde el borrador. |

## Comprobaciones sin bloqueante

- **§10–§13 → tareas**: complejidad/medidas/costes (T12–T16, T20), once pruebas §11 + replay/duplicado-revisión (T5, T18–T19; replay ya incluye duplicado/revisión en `replay.py`), memoria y rúbrica (T14–T17, T21–T22), transparencia §13 (T17, T21).
- **Paralelismo A / B / C+D**: no hay el mismo fichero de producción en bloques distintos; colisiones internas mitigadas (T3 tras T1+T2; T9∥T10 tras T8; `docs/MEMORIA.md` solo en C+D con cadena T15→T16→T17).
- **FR-019 / FR-020**: cubiertos en A (T1–T4) y B (T7–T10); verificación en E (T18–T19).
- **Constitución VI (REPRODUCCIÓN, sintéticos)**: coherente entre spec, plan y tareas; no se detectan desviaciones MUST pendientes de tarea.

## Veredicto

**Hay 2 hallazgos ALTOS (I1, I2)**. Conviene corregirlos en spec/tasks antes de `/speckit-implement`; el resto no bloquea el arranque de A, B y C+D en paralelo tras T0.
