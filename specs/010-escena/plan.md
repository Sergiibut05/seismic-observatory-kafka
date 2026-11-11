# Plan 010: escena del globo y panel responsive

- **Rama**: `010-escena` | **Spec**: [spec.md](./spec.md)
- **Stack**: el del panel (Angular 21, Vitest, globe.gl 2.46.2). `three` entra como dependencia directa, versión exacta la que resuelva globe.gl (`>= 0.179`). Sin Spark, Flink, Kubernetes ni ML.
- **Contrato**: no se toca. `/eventos/mapa` sigue con tope 5000. La cinta no viaja en la query.
- **Reabrir CSS**: `frontend/src/styles.css` y `frontend/src/app/app.css` (cerrados en T4 de 006) se editan aquí: tokens de escena y rejilla a pantalla completa / superficies móviles.

## Decisiones

1. **Estado de encuadre en `PanelUiStore`**, no en `FiltrosStore`. `enGlobo`, `superficie` (`mapa` | `tabla` | `analisis`), `filtrosAbiertos` y `campoFoco`. El recorte de la cinta vive solo en el componente del globo: al destruirlo o al volver a plano, desaparece.
2. **Un solo `app-filtros`**. En escritorio plano sigue en la columna. En móvil y en la escena se muestra como diálogo (el mismo formulario) al pulsar la frase. Los radios de vista (en directo / REPRODUCCIÓN) siguen siendo los de `app-vista-datos`; en globo esa franja de controles se oculta y la frase abre el diálogo, que incluye el modo.
3. **Tierra intacta**. globe.gl + textura de 008. Marcas: módulo `componentes/globo/mallas.ts` importado solo dentro de `iniciar()`, junto a `import('globe.gl')` e `import('three')`. Una `InstancedMesh` de columnas. Anillos: se mantiene `ringsData` de globe.gl (ya son mallas Three.js animadas) con `colorPulso` violeta; no se reintroduce el ámbar. País elegido: un solo `polygonsData`. Magnitud: `htmlElementsData`. Clic en columna: raycaster sobre la malla; clic en océano/país: `onGlobeClick` + punto en polígono puro.
4. **Paleta**. Cuerpo = `estiloCirculo` / profundidad. Pulso, cifra de magnitud y acento de escena: `#8B7CFF` / `#5B4DFF` / `#F2F0FF`. Fondo `#070B12`. Aro de selección `#ffffff`. `#ffd166` solo sale de `globo.ts`.
5. **Gráfica de escena**. Un `app-grafico-barras` alimentado por barras calculadas en puro a partir de los eventos del mapa ya recortados (hora, magnitud o profundidad). Así la cinta recorta globo y gráfica sin pedir a la API. En el plano, recuentos y distribuciones siguen leyendo la API.
6. **Responsive**. Corte de escritorio: `72rem` (el que ya usa `app.css`). Móvil: `display: none` de las superficies no elegidas; el DOM no se reordena. Escritorio plano: `position: sticky` en filtros y `--alto-mapa` pasa a `calc(100svh - var(--alto-cabecera))`.

## Constitución

- I–VII, IX: no aplican (no hay Compose, Kafka ni secretos nuevos).
- VIII: el panel sigue en Angular + Leaflet en el plano; globe.gl es ampliación ya aceptada en 008. `three` es la dependencia que globe.gl ya arrastra; se declara para importarla en el chunk del globo.

## Estructura

```text
frontend/src/app/
  nucleo/panel-ui.store.ts
  puro/globo.ts            # alturaColumna, colorPulso, recortarPorHora, marcasCinta, paisEnPunto, barrasEscena
  componentes/
    frase-filtros/
    superficies/
    globo/                 # escena, leyenda, cinta, cifra, gráfica, mallas.ts
    filtros/               # modo diálogo
  app.html / app.css       # clases rejilla--globo, rejilla--mapa|tabla|analisis, rejilla--filtros
```

## Pruebas

- Vitest: altura, violeta, ND, recorte, punto en polígono, barras de escena, frase (AC-1).
- jsdom: selector Plano/Globo vía store; conmutador de superficie; diálogo de filtros.
- Navegador: plano y globo en escritorio y ~360 px (AC-2). `npm run build` con three y globe.gl diferidos (AC-3).
