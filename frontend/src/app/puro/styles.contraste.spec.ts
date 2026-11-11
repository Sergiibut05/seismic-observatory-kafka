// SC-004 / FR-011 (011): contraste de los tokens de los dos temas, leídos de styles.css.
import { readFileSync } from 'node:fs';
import { contraste, luminancia } from './contraste';

// `ng test` se lanza desde frontend/.
const css = readFileSync(`${process.cwd()}/src/styles.css`, 'utf8');

function tokens(selector: string): Record<string, string> {
  const inicio = css.indexOf(selector);
  if (inicio < 0) throw new Error(`no está ${selector} en styles.css`);
  const bloque = css.slice(inicio, css.indexOf('\n}', inicio));
  const out: Record<string, string> = {};
  for (const m of bloque.matchAll(/--([\w-]+):\s*(#[0-9a-f]{3,6})\s*;/gi)) out[m[1]] = m[2];
  return out;
}

const TEMAS = {
  papel: tokens(":root[data-tema='papel'] {"),
  noche: tokens(":root[data-tema='noche'] {"),
};

/** [primer plano, fondo, mínimo] */
const PARES: [string, string, number][] = [
  ['tinta', 'fondo', 7],
  ['tinta', 'superficie', 7],
  ['tinta-suave', 'fondo', 4.5],
  ['tinta-suave', 'superficie', 4.5],
  ['acento', 'fondo', 4.5],
  ['acento', 'superficie', 4.5],
  ['sobre-acento', 'acento', 4.5],
  ['linea-fuerte', 'fondo', 3],
  ['linea-fuerte', 'superficie', 3],
  ['foco', 'fondo', 3],
  ['alerta-texto', 'alerta-fondo', 4.5],
  ['atencion-texto', 'atencion-fondo', 4.5],
  ['info-texto', 'info-fondo', 4.5],
  ['ok-texto', 'fondo', 4.5],
  ['sobre-oscuro', 'oscuro', 7],
  ['sobre-oscuro-suave', 'oscuro', 4.5],
  ['escena-tinta', 'escena-fondo', 7],
  ['escena-tinta-suave', 'escena-fondo', 4.5],
  // 011: marcas de las gráficas (≥ 3:1, mínimo para elementos gráficos)
  ['barra', 'superficie', 3],
  ['barra-activa', 'superficie', 3],
];

describe('contraste WCAG', () => {
  it('calcula los extremos', () => {
    expect(contraste('#000', '#fff')).toBeCloseTo(21);
    expect(contraste('#777777', '#777777')).toBe(1);
    expect(luminancia('#ffffff')).toBeCloseTo(1);
    expect(() => luminancia('violeta')).toThrow();
  });

  for (const [tema, t] of Object.entries(TEMAS)) {
    for (const [a, b, min] of PARES) {
      it(`${tema}: --${a} sobre --${b} ≥ ${min}:1`, () => {
        expect(t[a], `falta --${a}`).toBeDefined();
        expect(t[b], `falta --${b}`).toBeDefined();
        expect(contraste(t[a], t[b])).toBeGreaterThanOrEqual(min);
      });
    }
  }

  it('el acento ya no es violeta (SC-001)', () => {
    for (const t of Object.values(TEMAS)) expect(t['acento'].toLowerCase()).not.toBe('#9d91ff');
  });
});
