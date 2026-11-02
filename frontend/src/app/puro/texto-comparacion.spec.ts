import { ComparacionHistorica } from '../modelos/api';
import { cifrasComparacion, describirFiltrosEfectivos } from './texto-comparacion';

const base = (over: Partial<ComparacionHistorica> = {}): ComparacionHistorica => ({
  ventana_actual: { desde: '2026-11-01T16:00:00.000Z', hasta: '2026-11-02T16:00:00.000Z', eventos: 30 },
  historico_2025: { estado: 'cargado', eventos: 18250, dias: 365, media_diaria: 50 },
  cociente: 0.6,
  filtros_efectivos: { magnitud_min: 4, magnitud_max: null, pais: null, subregion: null },
  aviso: 'x',
  generated_at: '2026-11-02T16:00:00.000Z',
  ...over,
});

describe('cifrasComparacion', () => {
  it('cargado: cifras con formato español', () => {
    const c = cifrasComparacion(base());
    expect(c.ultimas24h).toBe('30');
    expect(c.mediaDiaria2025).toBe('50');
    expect(c.cociente).toBe('0,6');
    expect(c.historicoNoDisponible).toBe(false);
  });
  it('no_cargado: «no disponible», jamás 0', () => {
    const c = cifrasComparacion(
      base({
        historico_2025: { estado: 'no_cargado', eventos: null, dias: 0, media_diaria: null },
        cociente: null,
      }),
    );
    expect(c.mediaDiaria2025).toBe('no disponible');
    expect(c.eventos2025).toBe('no disponible');
    expect(c.cociente).toBe('no disponible');
    expect(c.historicoNoDisponible).toBe(true);
  });
  it('cociente null con histórico cargado también es «no disponible»', () => {
    expect(cifrasComparacion(base({ cociente: null })).cociente).toBe('no disponible');
  });
  it('0 eventos en las últimas 24 h es un 0 real', () => {
    const c = cifrasComparacion(base({ ventana_actual: { desde: 'a', hasta: 'b', eventos: 0 }, cociente: 0 }));
    expect(c.ultimas24h).toBe('0');
    expect(c.cociente).toBe('0');
  });
});

describe('describirFiltrosEfectivos', () => {
  it('magnitud mínima, país y subregión', () => {
    expect(describirFiltrosEfectivos({ magnitud_min: 4, magnitud_max: null, pais: null, subregion: null })).toBe(
      'magnitud ≥ 4,0 · país: todos · subregión: todas',
    );
    expect(
      describirFiltrosEfectivos({ magnitud_min: 4.5, magnitud_max: 6, pais: 'Chile', subregion: 'South America' }),
    ).toBe('magnitud ≥ 4,5 y magnitud ≤ 6,0 · país: Chile · subregión: South America');
  });
  it('sin límites de magnitud', () => {
    expect(describirFiltrosEfectivos({ magnitud_min: null, magnitud_max: null, pais: null, subregion: null })).toContain(
      'magnitud: sin límites',
    );
  });
});
