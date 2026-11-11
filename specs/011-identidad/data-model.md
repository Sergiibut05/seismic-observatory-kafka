# Modelo de datos 011

Sin tablas ni campos de API nuevos. Todo es estado de interfaz o proyección de respuestas ya tipadas.

## Tema

- `'papel' | 'noche'`. Por defecto `papel`.
- Persistencia: `localStorage['observatorio.tema']`. Valor desconocido o lectura fallida → `papel`.

## VistaMundo

- `lat`, `lng` (normalizada a [−180, 180)), `zoom` (zoom de Leaflet; `null` = nadie ha movido aún el mapa y se ajusta al ancho).
- Vive en `PanelUiStore`, no en filtros ni en la URL. No es una señal: solo se lee al cambiar de modo.
- Escriben: `moveend` del plano y el fin de un arrastre del globo (o `capturarVista` justo antes de volver al plano).

## PaletaMundo (por tema)

- `oceano`, `tierra`, `frontera`, `reticula`, `bordeCirculo`, `opacidadBorde`, `fondo`, `atmosfera` (o `null` en papel), `seleccion`, `paisRelleno`, `paisLado`, `paisBorde`.
