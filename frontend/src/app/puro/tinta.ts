// Gota de tinta de la transición entre temas (011). Puro: devuelve los `clip-path` de cada fotograma.
//
// La página nueva se descubre dentro de una mancha que nace en el botón y crece hasta cubrir la
// ventana. La mancha es un polígono: un círculo cuyo radio ondula con unas pocas ondas lentas que
// giran mientras crece, como una gota que se abre paso. Solo cambia geometría (`clip-path`), así
// que el navegador no recalcula ningún filtro: va fluida también en pantallas grandes.
//
// Al volver a papel los mismos fotogramas se recorren al revés sobre la página vieja: la tinta se
// recoge hacia el botón.

export const DURACION_TINTA_MS = 900;
/** Vértices del polígono: suficientes para que el borde se vea curvo a pantalla completa. */
export const PUNTOS = 96;
/** Fotogramas clave; entre ellos el navegador interpola vértice a vértice. */
export const FOTOGRAMAS = 28;
/** Amplitud total de la ondulación, en fracción del radio. */
export const ONDULACION = 0.11;
/** El radio final sobra lo justo para que ni el valle más hondo deje una esquina sin cubrir. */
export const MARGEN_FINAL = 1 / (1 - ONDULACION) + 0.04;

export interface OpcionesTinta {
  ancho: number;
  alto: number;
  /** Origen en píxeles de la ventana. */
  x: number;
  y: number;
  /** Cambia el dibujo de la mancha de una vez a otra. */
  semilla?: number;
}

/** Distancia del origen a la esquina más lejana. */
export function radioFinal(o: Pick<OpcionesTinta, 'ancho' | 'alto' | 'x' | 'y'>): number {
  const dx = Math.max(o.x, o.ancho - o.x);
  const dy = Math.max(o.y, o.alto - o.y);
  return Math.max(1, Math.hypot(dx, dy));
}

/** Avance del radio (0..1): casi constante, con un aterrizaje suave (al recoger, un arranque suave). */
export function avance(p: number): number {
  const q = Math.min(1, Math.max(0, p));
  return 1 - Math.pow(1 - q, 1.3);
}

/** Ondas del borde: [lóbulos, peso, giro durante la transición en radianes]. Los pesos suman 1. */
const ONDAS: readonly (readonly [number, number, number])[] = [
  [2, 0.34, 1.1],
  [3, 0.3, -1.7],
  [5, 0.22, 2.4],
  [8, 0.14, -3.1],
];

/** Fase reproducible de cada onda a partir de la semilla. */
function fases(semilla: number): number[] {
  let s = (Math.abs(Math.round(semilla)) % 9973) + 1;
  return ONDAS.map(() => {
    s = (s * 16807) % 2147483647;
    return (s / 2147483647) * Math.PI * 2;
  });
}

/** Factor del radio en el ángulo `a` y el avance `p`: siempre dentro de 1 ± ONDULACION. */
export function ondulacion(a: number, p: number, fase: readonly number[]): number {
  let n = 0;
  ONDAS.forEach(([k, peso, giro], i) => {
    n += peso * Math.sin(k * a + fase[i] + giro * p);
  });
  return 1 + ONDULACION * n;
}

const px = (n: number) => `${Math.round(n * 10) / 10}px`;

/**
 * `clip-path` de cada fotograma, de la gota recién nacida a la ventana cubierta. Todos tienen los
 * mismos vértices, así que se interpolan entre sí.
 */
export function fotogramasTinta(o: OpcionesTinta): string[] {
  const fase = fases(o.semilla ?? 7);
  const total = radioFinal(o) * MARGEN_FINAL;
  const salida: string[] = [];
  for (let f = 0; f < FOTOGRAMAS; f++) {
    const p = f / (FOTOGRAMAS - 1);
    const radio = total * avance(p);
    const puntos: string[] = [];
    for (let i = 0; i < PUNTOS; i++) {
      const a = (i / PUNTOS) * Math.PI * 2;
      const r = radio * ondulacion(a, p, fase);
      puntos.push(`${px(o.x + Math.cos(a) * r)} ${px(o.y + Math.sin(a) * r)}`);
    }
    salida.push(`polygon(${puntos.join(', ')})`);
  }
  return salida;
}
