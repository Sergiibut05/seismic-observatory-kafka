# Contrato de interfaz 010

La API HTTP no cambia (`docs/CONTRATO-API.md`). Este contrato es solo de UI.

## Clases en `main#contenido`

| Clase | Cuándo |
|---|---|
| `rejilla--globo` | `PanelUiStore.enGlobo === true` |
| `rejilla--mapa` / `rejilla--tabla` / `rejilla--analisis` | superficie móvil (ignorada en escritorio y en globo) |
| `rejilla--filtros` | diálogo de filtros abierto |

## Eventos de la escena (locales)

| Acción | Efecto | API |
|---|---|---|
| Mover cinta a instante T | Oculta features con `ocurrencia > T` en globo y gráfica de escena | ninguna |
| Clic en país con `ADM0_A3` en opciones | `FiltrosStore.editar({ pais })` + `aplicarYa()` | ronda normal de filtros |
| Clic en evento | `eventoSeleccionado` (igual que 008) | ninguna |
| Volver a Plano | `enGlobo=false`; recorte de cinta anulado | ninguna |

## Paleta de acento (globo)

| Uso | Valor |
|---|---|
| Pulso / cifra magnitud, M < 4 | `#8B7CFF` |
| 4 ≤ M < 6 | `#5B4DFF` |
| M ≥ 6 | `#F2F0FF` |
| ND pulso | `#c8d0d8` |
| Fondo escena | `#070B12` |
| Aro selección | `#ffffff` |
