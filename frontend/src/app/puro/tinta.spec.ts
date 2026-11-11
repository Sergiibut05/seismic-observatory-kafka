import {
  FOTOGRAMAS,
  MARGEN_FINAL,
  ONDULACION,
  PUNTOS,
  avance,
  fotogramasTinta,
  ondulacion,
  radioFinal,
} from './tinta';

/** Vértices de un `polygon(...)` en píxeles. */
function vertices(clip: string): [number, number][] {
  return [...clip.matchAll(/(-?[\d.]+)px (-?[\d.]+)px/g)].map((m) => [Number(m[1]), Number(m[2])]);
}

describe('gota de tinta', () => {
  const base = { ancho: 1440, alto: 900, x: 1400, y: 20 };

  it('el radio final se mide hasta la esquina más lejana del botón', () => {
    expect(radioFinal(base)).toBeCloseTo(Math.hypot(1400, 880));
    expect(radioFinal({ ...base, x: 0, y: 0 })).toBeCloseTo(Math.hypot(1440, 900));
  });

  it('el avance va de 0 a 1 sin retroceder', () => {
    expect(avance(0)).toBe(0);
    expect(avance(1)).toBe(1);
    let antes = 0;
    for (let p = 0.05; p <= 1; p += 0.05) {
      expect(avance(p)).toBeGreaterThan(antes);
      antes = avance(p);
    }
  });

  it('todos los fotogramas tienen los mismos vértices (se pueden interpolar)', () => {
    const f = fotogramasTinta(base);
    expect(f).toHaveLength(FOTOGRAMAS);
    for (const clip of f) {
      expect(clip).toMatch(/^polygon\(/);
      expect(vertices(clip)).toHaveLength(PUNTOS);
    }
  });

  it('nace como un punto en el botón', () => {
    for (const [x, y] of vertices(fotogramasTinta(base)[0])) {
      expect(x).toBeCloseTo(1400);
      expect(y).toBeCloseTo(20);
    }
  });

  it('la ondulación nunca se sale de su amplitud', () => {
    const fase = [0.3, 1.2, 2.5, 4.1];
    for (let a = 0; a < Math.PI * 2; a += 0.05) {
      for (const p of [0, 0.3, 0.7, 1]) {
        const k = ondulacion(a, p, fase);
        expect(k).toBeGreaterThanOrEqual(1 - ONDULACION - 1e-9);
        expect(k).toBeLessThanOrEqual(1 + ONDULACION + 1e-9);
      }
    }
    expect(MARGEN_FINAL * (1 - ONDULACION)).toBeGreaterThan(1);
  });

  it('al terminar cubre toda la ventana: ningún vértice queda dentro del radio de la esquina', () => {
    for (const origen of [
      base,
      { ancho: 390, alto: 844, x: 360, y: 24 },
      { ancho: 1920, alto: 1080, x: 960, y: 540 },
    ]) {
      for (const semilla of [1, 42, 9999]) {
        const ultimo = vertices(fotogramasTinta({ ...origen, semilla }).at(-1)!);
        const minimo = Math.min(...ultimo.map(([x, y]) => Math.hypot(x - origen.x, y - origen.y)));
        expect(minimo).toBeGreaterThan(radioFinal(origen));
      }
    }
  });

  it('la mancha solo crece: cada vértice se aleja del botón de un fotograma al siguiente', () => {
    const f = fotogramasTinta(base).map(vertices);
    for (let i = 1; i < f.length; i++) {
      const media = (v: [number, number][]) =>
        v.reduce((s, [x, y]) => s + Math.hypot(x - base.x, y - base.y), 0) / v.length;
      expect(media(f[i])).toBeGreaterThan(media(f[i - 1]));
    }
  });

  it('la semilla cambia el dibujo y no se rompe con tamaños nulos', () => {
    expect(fotogramasTinta({ ...base, semilla: 1 })[10]).not.toBe(
      fotogramasTinta({ ...base, semilla: 2 })[10],
    );
    expect(() => fotogramasTinta({ ancho: 0, alto: 0, x: 0, y: 0 })).not.toThrow();
  });
});
