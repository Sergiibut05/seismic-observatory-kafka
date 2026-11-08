# Comprobación documental T20 — `docs/MEMORIA.md`

Fecha verificación: 2026-11-08 (~14:42 UTC). Rama: `007-memoria`.

## Criterios de aceptación (spec §12)

| AC | Veredicto | Notas |
| --- | --- | --- |
| **AC-1** entrada única y enlaces | **PASA** | Índice §1–§18 con anclas; **39 enlaces relativos** comprobados con `Test-Path` desde `docs/` → todos resuelven. §12 y §13 aún dicen «pendiente de F/E» pero enlazan a capturas/evidencias previstas. |
| **AC-2** diccionario vs `information_schema` | **PASA** | §2.2 enumera las 11 tablas y **99 columnas** (14+12+14+12+10+12+3+6+9+4+3). `SELECT count(*) …` en vivo → **99**. Recuentos por tabla coinciden con el diccionario (p. ej. `ingesta.cuarentena` 9). Definición completa en `consultas.resultado.txt` **Q02** (2026-11-08). |
| **AC-3** 18.302 histórico | **PASA** | `SELECT count(*) FROM historico.evento_2025` → **18302** (= 18.302 en memoria). Cita **Q11** y manifiesto. Hueco noviembre: **§3.5** + consultas (Q10). |
| **AC-4** calidad §5 (seis dimensiones) | **PASA** (muestreo) | §5.1–5.7 con consultas **Q12–Q25**, resultados en `consultas.resultado.txt`, acciones y limitaciones. No se re-ejecutaron las 31 consultas en esta sesión. |
| **AC-5** análisis §8 / §12 | **PARCIAL** | **Capturas** listas (`analisis-*.png`) con filtros anotados abajo y M≥4 en comparación. **`docs/MEMORIA.md` §12** aún sin las tres conclusiones escritas («las añade F», T21 pendiente). |
| **AC-6** complejidad §10 | **PASA** (muestreo) | §7–§8 + `memoria/mediciones.md` con M1–M6, tamaños 1k/10k/100k, limpieza `medicion.` documentada. |
| **AC-7** índice y 100M | **PASA** (muestreo) | §4.4 índices con Q30; §9 extrapolación; mediciones con y sin índice en M5. |
| **AC-17** explicación individual | **PASA** | §15 con huecos `[ESCRIBE: …]` sin rellenar por agente. Sin URL Netlify ni authtoken en memoria (§14 «PENDIENTE (alumno)»). |
| **AC-18** rúbrica §17 | **PASA** (estructura) | §17 enlaza criterios del enunciado a secciones y ficheros (`comandos.md`, `consultas.sql`, evidencias). Tabla de aceptación §13 aún «pendiente de E» (T18 tiene `aceptacion.md` aparte). |

## Enlaces rotos

Ninguno en el muestreo automático de rutas relativas desde `docs/MEMORIA.md` (incluye `../specs/…`, `memoria/…`, `ENUNCIADO.md`, `compose.yaml`).

## Cifras sin `Qnn` / comando / fecha

Muestreo: las cifras de procedencia y calidad citan **Q07–Q25**, **C1–C9** o fecha explícita (p. ej. «14:23 UTC del 2026-11-08»). Excepción menor ya declarada en memoria: latencia USGS «muestra aparte de 8 peticiones (C3)» sin tabla completa en §2.1 — no bloqueante.

## Secretos en Git

`git grep -i -E "authtoken|password="` → solo documentación, tests con contraseñas ficticias, `.env.example` con `POSTGRES_PASSWORD=` vacío. **PASA** (sin credenciales reales en índice).

---

## Capturas de análisis (interruptor sintéticos **apagado**, modo **En directo**)

Hora de referencia en barra de estado del panel: **~14:41–14:42 UTC** (último acceso correcto a la API).

### `analisis-1.png` (conclusión 1 — país, sin filtro de magnitud)

| Campo | Valor |
| --- | --- |
| Filtros | `desde=2026-11-07T14:34`, `hasta=2026-11-08T14:36` (ventana ~24 h), magnitud min/max vacíos, país/subregión todos, sintéticos **OFF**, En directo |
| Hora UTC | ~**14:34** (sesión T19; misma vista que `02-filtros-aplicados.png`) |
| Cifras visibles | Total periodo **204**; **Estados Unidos 143**; resto de barras coherentes con suma 204 |

### `analisis-1b.png` (conclusión 1 — M≥4)

| Campo | Valor |
| --- | --- |
| Filtros | Misma ventana 24 h, **magnitud mínima 4**, sintéticos OFF |
| Hora UTC | **~14:41 UTC** |
| Cifras visibles | Total **21**; **Sin país asignado 14** (domina); **Estados Unidos ausente** del gráfico; comparación en captura: 21 / media 50,1 / 0,42 |

### `analisis-2.png` (conclusión 2 — comparación histórica)

| Campo | Valor |
| --- | --- |
| Filtros | Ventana 24 h (~`2026-11-07T14:40`–`2026-11-08T14:41`), sin magnitud en recuentos; comparación con **magnitud efectiva ≥ 4** |
| Hora UTC | **~14:41 UTC** |
| Cifras visibles | Últimas 24 h **21** eventos; media diaria 2025 **50,1** (base **18.302** eventos / 365 días); cociente **0,42** |

### `analisis-3.png` (conclusión 3 — profundidad sin filtro mag.)

| Campo | Valor |
| --- | --- |
| Filtros | Ventana 24 h, sin magnitud mínima, sintéticos OFF |
| Hora UTC | **~14:41 UTC** |
| Cifras visibles | **204** eventos; profundidad dominante **0–10 km** (mayor barra en captura) |

### `analisis-3b.png` (profundidad con M≥4)

| Campo | Valor |
| --- | --- |
| Filtros | Ventana 24 h, **magnitud mínima 4** |
| Hora UTC | **~14:41 UTC** |
| Cifras visibles | **21** eventos; profundidad dominante **10–30 km** (11 eventos en captura); magnitud dominante banda **4–5** |

---

## Fallos / pendientes para el developer (documental)

1. **§12 MEMORIA**: falta redactar las tres conclusiones enlazando estas capturas (T21).
2. **§13 tabla**: sigue en «pendiente de E» en memoria aunque exista `evidencias/aceptacion.md` — alinear en T21.
3. **§16**: texto «T11 sigue abierta» debería actualizarse tras T19 (T22/T23).
4. **Coherencia de totales en panel** (no documental pero afecta análisis): ver `verificacion.md` (480 vs 203 en recuentos por país).
