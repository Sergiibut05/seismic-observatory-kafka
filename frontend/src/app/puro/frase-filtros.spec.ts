import { VistaDatos } from './filtros';
import { textoMagnitud, textoVentana, trozosFrase } from './frase-filtros';

const vivo: VistaDatos = { modo: 'live', sinteticos: false };

describe('trozosFrase', () => {
  it('sin filtros: modo en directo y «todos»', () => {
    const t = trozosFrase(vivo, {});
    expect(t.map((x) => x.texto)).toEqual([
      'En directo',
      'todas las magnitudes',
      'todos los países',
      'todo el periodo',
    ]);
  });

  it('magnitud mínima y país se leen tal cual, sin inventar el máximo', () => {
    expect(textoMagnitud({ magnitudMin: 4 })).toContain('4,0');
    expect(textoVentana({ desde: '2026-11-01T00:00' })).toBe('2026-11-01T00:00');
    const t = trozosFrase({ modo: 'replay', sinteticos: false }, { magnitudMin: 4, pais: 'CHL' }, undefined, 'Chile');
    expect(t[0].texto).toBe('REPRODUCCIÓN');
    expect(t[2].texto).toBe('Chile');
  });
});
