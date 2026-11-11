# Contrato de interfaz 011

La API HTTP no cambia (`docs/CONTRATO-API.md`).

## Atributos, clases y variables en `<html>`

| Marca | Cuándo |
|---|---|
| `data-tema="papel"` / `data-tema="noche"` | siempre; lo pone `index.html` antes del primer pintado y luego `TemaService` |
| `.cambiando-tema` + `.tema-derrama` o `.tema-recoge` + `--tinta-x` / `--tinta-y` | solo durante la transición de tinta |
| `.vt-globo-entra` / `.vt-globo-sale` | solo durante la transición plano ↔ globo |

## Tokens (extracto)

| Token | Papel | Noche |
|---|---|---|
| `--fondo` | `#F4F1EA` | `#070B12` |
| `--superficie` | `#FBF9F4` | `#101820` |
| `--tinta` | `#1A1A1A` | `#E8EEF3` |
| `--tinta-suave` | `#5C574E` | `#9AA8B8` |
| `--linea-fuerte` | `#8A8377` | `#6D7E90` |
| `--acento` (rojo de pluma) | `#C8102E` | `#FF6B5E` |
| `--barra` / `--barra-activa` | `#3F7F86` / `#1D4F55` | `#6FB3B2` / `#C4EBE7` |
| `--foco` | `#1A1A1A` | `#FFD166` |

## Mundo

| Uso | Papel | Noche |
|---|---|---|
| Océano | `#C5D1CF` | `#08141E` |
| Tierra | `#F7F3EA` | `#22393C` |
| Frontera | `#6F685C` | `#4D6D70` |
| Contorno de círculo | `#1A1A1A` al 60 % | `#E8EEF3` al 45 % |
| Fondo de escena | `#F4F1EA` | `#070B12` |
| Selección de evento | `#C8102E` | `#FFFFFF` |
| País pulsado | tinta al 16 %, borde `#1A1A1A` | blanco al 22 %, borde `#FFFFFF` |

## Pulsos del globo

| Magnitud | Papel | Noche |
|---|---|---|
| M < 4 | `#E07A86` | `#FF9A90` |
| 4 ≤ M < 6 | `#C8102E` | `#FF6B5E` |
| M ≥ 6 | `#7A0019` | `#FFE3DF` |
| ND | `#9A9385` | `#C8D0D8` |

## Eventos locales

| Acción | Efecto | API |
|---|---|---|
| Botón de tema | `TemaService.alternar(origen)`; gota de tinta (se derrama a noche, se recoge a papel) | ninguna |
| Plano → Globo | recorte desde el marco; el globo se abre en `vistaMundo` | ninguna |
| Globo → Plano | `capturarVista()`; recorte hacia el marco; el plano se centra en `vistaMundo` | ninguna |
