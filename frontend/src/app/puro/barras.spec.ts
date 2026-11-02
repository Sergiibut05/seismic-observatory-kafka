import {
  DatoBarra,
  acortar,
  calcularBarras,
  escalaMaxima,
  etiquetaHoraUtc,
  etiquetaVentanaUtc,
  indicesEtiquetasVisibles,
  marcasEscala,
  principalesConResto,
  textoAlternativo,
  tipoDeBarra,
} from './barras';

const d = (clave: string, valor: number | null, extra: Partial<DatoBarra> = {}): DatoBarra => ({
  clave,
  etiqueta: clave,
  valor,
  ...extra,
});

describe('escalaMaxima y marcasEscala', () => {
  it('redondea hacia arriba a 1, 2, 2,5, 5 × 10^k', () => {
    expect(escalaMaxima([0, 0])).toBe(1);
    expect(escalaMaxima([7])).toBe(10);
    expect(escalaMaxima([33])).toBe(50);
    expect(escalaMaxima([120, 47])).toBe(200);
    expect(escalaMaxima([200, null])).toBe(200);
    expect(escalaMaxima([210])).toBe(250);
    expect(escalaMaxima([2])).toBe(2);
  });
  it('ignora null y no usa nunca un máximo menor que un valor', () => {
    for (const v of [1, 3, 9, 11, 26, 99, 101, 999, 1234]) expect(escalaMaxima([v, null])).toBeGreaterThanOrEqual(v);
  });
  it('marcas enteras de 0 al máximo', () => {
    expect(marcasEscala(1)).toEqual([0, 1]);
    expect(marcasEscala(20)).toEqual([0, 5, 10, 15, 20]);
    expect(marcasEscala(250)).toEqual([0, 50, 100, 150, 200, 250]);
    expect(marcasEscala(0)).toEqual([0]);
  });
});

describe('calcularBarras', () => {
  it('el cero es una barra de tipo «cero» (no ND) y el null es «nd» sin longitud', () => {
    const b = calcularBarras([d('a', 10), d('b', 0), d('c', null)], 10);
    expect(b.map((x) => x.tipo)).toEqual(['normal', 'cero', 'nd']);
    expect(b[0].fraccion).toBe(1);
    expect(b[1].fraccion).toBe(0);
    expect(b[1].valorTexto).toBe('0');
    expect(b[2].valorTexto).toBe('ND');
    expect(b[2].valor).toBeNull();
  });
  it('«sin valor» es un tipo propio, también con valor 0', () => {
    expect(tipoDeBarra(d('s', 2, { sinValor: true }))).toBe('sin-valor');
    expect(tipoDeBarra(d('s', 0, { sinValor: true }))).toBe('sin-valor');
    expect(calcularBarras([d('s', 2, { sinValor: true })], 10)[0].fraccion).toBe(0);
  });
  it('mantiene una barra por categoría y la etiqueta corta por defecto es la completa', () => {
    const b = calcularBarras([d('a', 1), d('b', 0)], 1);
    expect(b).toHaveLength(2);
    expect(b[0].etiquetaCorta).toBe('a');
  });
});

describe('indicesEtiquetasVisibles', () => {
  it('muestra todas si caben', () => {
    expect(indicesEtiquetasVisibles(5, 8)).toEqual([0, 1, 2, 3, 4]);
  });
  it('reparte de forma uniforme si no caben', () => {
    expect(indicesEtiquetasVisibles(24, 8)).toEqual([0, 3, 6, 9, 12, 15, 18, 21]);
    expect(indicesEtiquetasVisibles(48, 12)).toEqual([0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44]);
  });
  it('casos límite', () => {
    expect(indicesEtiquetasVisibles(0, 5)).toEqual([]);
    expect(indicesEtiquetasVisibles(10, 1)).toEqual([0]);
  });
});

describe('textos', () => {
  it('acorta con elipsis', () => {
    expect(acortar('Estados Unidos de América', 10)).toBe('Estados U…');
    expect(acortar('Chile', 10)).toBe('Chile');
  });
  it('etiquetas de hora en UTC', () => {
    expect(etiquetaHoraUtc('2026-11-01T16:00:00.000Z')).toBe('16:00');
    expect(etiquetaVentanaUtc('2026-11-01T05:00:00.000Z')).toBe('01/11 05:00 UTC');
    expect(etiquetaHoraUtc('basura')).toBe('ND');
  });
  it('texto alternativo: total, mayor, ceros, sin valor y ND', () => {
    const barras = calcularBarras(
      [d('Chile', 5), d('Perú', 0), d('Japón', 2), d('Sin valor', 2, { sinValor: true }), d('X', null)],
      5,
    );
    const t = textoAlternativo('Eventos por país', barras, 'eventos');
    expect(t).toContain('Eventos por país.');
    expect(t).toContain('5 categorías, 9 eventos en total.');
    expect(t).toContain('Mayor: Chile, 5.');
    expect(t).toContain('1 categorías con 0.');
    expect(t).toContain('Sin valor: 2.');
    expect(t).toContain('1 categorías con valor desconocido (ND).');
  });
  it('texto alternativo sin categorías', () => {
    expect(textoAlternativo('T', [], 'eventos')).toBe('T. Sin categorías que mostrar.');
  });
});

describe('principalesConResto', () => {
  const datos = [d('A', 50), d('B', 40), d('Sin país asignado', 1), d('C', 30), d('D', 20), d('E', 10)];
  it('no toca listas cortas', () => {
    expect(principalesConResto(datos, 10)).toHaveLength(6);
  });
  it('conserva las obligatorias y suma el resto sin perder eventos', () => {
    const r = principalesConResto(datos, 3, ['Sin país asignado']);
    expect(r.map((x) => x.etiqueta)).toEqual(['A', 'B', 'Sin país asignado', 'Resto (3)']);
    expect(r.reduce((s, x) => s + (x.valor ?? 0), 0)).toBe(151);
  });
});
