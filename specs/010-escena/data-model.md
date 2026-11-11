# Modelo de datos 010

Sin tablas nuevas. Todo es estado de interfaz sobre la respuesta ya tipada de `/eventos/mapa` y `/comparacion-historica`.

## RecorteCinta

- `corte`: `string | null` (ISO UTC). `null` = sin recorte (equivalente al extremo derecho).
- Regla: se oculta el evento con `ocurrencia` estrictamente posterior a `corte`.
- No se serializa a la API. Muere al salir del globo.

## MarcaCinta

- `id`, `ocurrencia`, `t` ∈ [0, 1] sobre la ventana [fin − 24 h, fin], donde `fin` es el máximo entre ahora y la última ocurrencia cargada.
- Eventos anteriores a la ventana: `t = 0`.

## ColumnaGlobo (proyección pura)

- De `EventoMapa`: `id`, `lat`, `lng`, `color` (profundidad), `altura` (`alturaColumna`), `radio`, `props`.
- `alturaColumna(null)` = stub constante, distinta de tratar el nulo como magnitud 0 para el color.

## PaisIluminado

- `ADM0_A3` del feature en `paises-globo.geojson` que contiene el clic.
- Relación: el país persistido del evento no se recalcula; solo se escribe `FiltrosEditados.pais` si el código está en las opciones de `/recuentos/pais`.

## FraseFiltros

- `modo`: live | replay
- `magnitud`: texto del mínimo/máximo aplicado o «todos»
- `pais`: nombre visible o «todos»
- `ventana`: rango ISO o «todo el periodo»
