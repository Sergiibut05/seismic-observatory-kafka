# Research 011

## Dirección visual

- **Decisión**: papel y tinta. Papel crema, tinta, rojo de pluma para lo que importa, serif para la marca y los títulos, cifras en mono, y formas suaves (esquinas redondeadas, píldoras). Modo noche con la base de color anterior.
- **Razón**: aleja el panel del dashboard oscuro genérico (negro + violeta + vidrio) que comparten muchas entregas, sin perder cercanía.
- **Probado y descartado**: un estilo de instrumento muy cuadrado (esquinas de 2 px, versalitas, segmentados rectos): el usuario lo vio formal y frío. Un titular de 24 h a modo de portada: parecía una landing. Un helicorder de 24 h como pieza firma: ocupaba mucho y competía con el mapa sin aportar más que la gráfica por hora.

## Un solo mundo, sin teselas

- **Decisión**: plano y globo dibujan Natural Earth con la misma paleta por tema.
- **Razón**: las teselas claras eran la única superficie clara de una app oscura; plano y globo parecían dos productos. Además se quita un tercero.
- **Coste**: sin ciudades ni carreteras al ampliar; zoom máximo 8, lo que aguanta la geometría 1:50m.
- **Alternativa**: teselas oscuras de CARTO (casi igual de integradas, pero no idénticas al globo y con un tercero).
- **Papel**: océano `#C5D1CF`, tierra `#F7F3EA`, frontera `#6F685C`. Un primer intento más claro dejaba el globo casi blanco bajo las luces.

## Transición plano ↔ globo

- **Primer intento** (`view-transition-name` en el marco del mapa): el navegador escalaba la instantánea del mapa con sus círculos hasta pantalla completa y la fundía con la escena, mientras la raíz hacía su propio fundido: círculos gigantes y borrosos y dos cabeceras a la vez.
- **Decisión**: recorte geométrico (`clip-path`) desde el marco del mapa. Ninguna instantánea se escala; solo cambia qué parte se ve.

## Transición de tinta

- **Decisión**: una gota. La página nueva se recorta con un polígono (`clip-path`) de 96 vértices: un círculo centrado en el botón cuyo radio ondula con cuatro ondas lentas (2, 3, 5 y 8 lóbulos) que giran mientras crece. Se dan 28 fotogramas clave y el navegador interpola vértice a vértice. A noche, la gota se derrama sobre la página vieja; a papel, los mismos fotogramas van al revés sobre la vieja, que queda encima: la tinta se recoge hacia el botón. 0,9 s.
- **Razón**: solo cambia geometría. Ningún filtro se recalcula en cada fotograma, así que va fluida en pantallas grandes y de alta densidad, y el borde es nítido a cualquier tamaño.
- **Cobertura**: la ondulación vale como mucho ±11 % del radio y el radio final sobra un 16 %: ni el valle más hondo deja una esquina sin cubrir (lo comprueba el test con tres tamaños de ventana y tres semillas).
- **Descartado: máscara marmolada con filtros SVG** (la primera versión de esta feature). Campo fijo (degradado + `feTurbulence`) y un umbral animado con SMIL. Dio tres vueltas de ajuste (islas del tema viejo, barrido visible de solo 0,3 s, terrazas grises por los 8 bits del filtro) y aun afinada dependía de recalcular el filtro a media resolución en cada fotograma: 1,9 s y un frente borroso. El usuario pidió rehacerla.
- **Otras alternativas**: `clip-path: circle()` (igual de fluido, pero genérico: es la transición de tema de media web); un shader WebGL (no puede leer las instantáneas de la página).
- **Detalle**: la animación lleva `fill: both`; al terminar la transición se cancela, porque si no seguiría viva sobre un pseudoelemento que ya no existe.

### Segunda vuelta: la escena se revelaba a medias

Medido en Chrome: la transición arrancaba a los 78 ms, pero el globo seguía en «Cargando el globo…» hasta los 651 ms (cuando ya estaba la mitad del recorte hecho) y entonces aparecía de golpe; después llegaba la textura de la Tierra (un PNG de 4096 × 2048 que se codificaba en ese momento) y las columnas. Al volver, Leaflet recuperaba su tamaño después de capturar el estado nuevo. El recorte era correcto; lo que se recortaba, no.

- **Decisión**: preparar antes de congelar y mantener congelada la página vieja hasta que el estado nuevo está completo.
  1. `precarga.ts` guarda los módulos del globo, las fronteras y la textura de cada tema (también al cambiar de tema dentro del globo: ya no se vuelve a dibujar). El plano la dispara en un momento de calma (`requestIdleCallback`) o al acercarse al botón; sin ahorro de datos.
  2. `fijarGlobo(true)` espera a esa precarga **antes** de `startViewTransition` (con la página viva; 4 s como máximo). Si aún no está, el cursor pasa a «progreso».
  3. El callback de `startViewTransition` devuelve una promesa: monta el globo y espera a que avise de que tiene textura y columnas (2,5 s como máximo). Al salir, el plano se reencuadra y se redimensiona de forma síncrona dentro del callback.
- **Medición**: Chrome congela `requestAnimationFrame` mientras corre el callback, pero no los temporizadores ni la carga de imágenes. Por eso el globo espera a su textura sondeando `material.map` con temporizadores, no con el bucle de dibujo.
- **Resultado**: al arrancar el recorte, el globo ya tiene canvas, textura y columnas (antes, a los 651 ms ni siquiera había canvas); la vuelta empieza con el plano ya a su tamaño.
- **Además**: la escena nueva nace recortada (`--recorte-inicial`) para que no haya un fotograma a pantalla completa antes de que arranque la animación, y se ignoran las pulsaciones mientras hay una transición en curso (antes, un doble clic encadenaba dos transiciones).

## Globo

- **Columnas**: con la escala de 008 M5 medía un tercio del radio y el globo parecía un erizo; ahora crecen de forma cuadrática y M7 queda por debajo de 0,2 radios.
- **Contorno de tinta** (casco invertido: misma geometría, algo más gruesa, pintada por detrás): la columna amarilla de 0–10 km se lee sobre papel sin tocar la escala de profundidad.
- **País pulsado**: realce neutro de tinta; el rojo queda para la selección de eventos.

## Gráficas (guía de visualización de datos)

- Un solo tono para una sola serie, azul océano para enlazar con el globo, ≥ 3:1 sobre la superficie.
- Poner el valor en todas las barras verticales es un antipatrón: queda en la máxima; el resto lo dan el eje, la ficha y la tabla equivalente. En la lista ordenada por país sí va en la punta de cada barra, que es donde se lee una clasificación.
- Zona de puntería mayor que la marca; ficha junto a la barra; el resto se atenúa al 40 %.
- Los eventos de puntero van en el `<g>` de cada barra: en la zona de puntería (hermana de la barra) no saltaban con el puntero encima de la barra.
- **Lienzo a tamaño real**: antes el SVG tenía un `viewBox` fijo de 720 unidades y se escalaba al ancho de la tarjeta, así que un texto de 11 px se quedaba en 7–8. Ahora un `ResizeObserver` mide el contenedor y una unidad es un píxel. Sin `ResizeObserver` (jsdom) se usa un ancho de partida.
- **Rejilla continua, no discontinua**: la línea discontinua se reserva para la referencia (la media por hora), que es lo que significa.
- **Lista por país sin eje**: con el valor en la punta y la parte del total a la derecha, el eje de valores sobraba.
- **Comparación histórica**: tres fichas con un número cada una obligaban a comparar de memoria. Dos barras sobre la misma escala lo enseñan; la de 2025 va en gris porque es la referencia. El cociente se acompaña de su lectura en palabras, en tinta neutra: estar por encima o por debajo de la media no es bueno ni malo, y el panel no evalúa riesgo.
- **Profundidad**: colorear las barras con la escala del mapa dejaba la de 0–10 km (amarillo claro) sin contraste sobre papel. La escala va como clave bajo el eje, con el mismo contorno de tinta que los círculos, y las barras siguen en un tono.
- **Sin librería**: se valoró una librería de gráficos. Lo que faltaba era acabado (tamaño real, ficha, datos clave), no tipos de gráfica, y el SVG propio ya cumple los requisitos de accesibilidad de 006 (cero, sin valor y ND distintos; tabla equivalente).

## Tipografía

- **Decisión**: IBM Plex Serif, Sans y Mono desde `@fontsource`, subconjunto latino. Una familia con tres voces; OFL; empaquetada, cumple «sin CDN».

## Presupuesto del bundle

- El aviso de `angular.json` pasa de 575 kB a 625 kB (error en 1 MB). Medido: ≈ 590 kB (150 kB transferidos). `mapa.css` supera el aviso por componente (6 kB) y queda bajo el error (8 kB).
