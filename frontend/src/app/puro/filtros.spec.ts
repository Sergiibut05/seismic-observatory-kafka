import {
  FILTROS_VACIOS,
  FiltrosAplicados,
  FiltrosEditados,
  SIN_PAIS,
  VISTA_VIVO,
  VistaDatos,
  aQuery,
  acotarVentanaHora,
  notaOrigenDatos,
  validarFiltros,
} from './filtros';

const editados = (parcial: Partial<FiltrosEditados> = {}): FiltrosEditados => ({
  ...FILTROS_VACIOS,
  ...parcial,
});

const DIA = 24 * 3600 * 1000;

describe('validarFiltros', () => {
  it('vacío: válido y sin ningún campo', () => {
    const r = validarFiltros(editados());
    expect(r).toEqual({ ok: true, filtros: {} });
  });

  it('interpreta las fechas como UTC y las serializa con Z y milisegundos', () => {
    const r = validarFiltros(editados({ desde: '2026-11-01T10:30', hasta: '2026-11-02T00:00' }));
    expect(r).toEqual({
      ok: true,
      filtros: { desde: '2026-11-01T10:30:00.000Z', hasta: '2026-11-02T00:00:00.000Z' },
    });
  });

  it('acepta segundos, milisegundos y una Z final', () => {
    const r = validarFiltros(editados({ desde: '2026-01-01T00:00:05.5Z' }));
    expect(r).toEqual({ ok: true, filtros: { desde: '2026-01-01T00:00:05.500Z' } });
  });

  it('rechaza fechas mal formadas o inexistentes', () => {
    for (const desde of ['ayer', '2026-02-30T10:00', '2026-11-01', '2026-11-01T10:00+02:00']) {
      const r = validarFiltros(editados({ desde }));
      expect(r.ok, desde).toBe(false);
      if (!r.ok) expect(r.errores.desde).toBeTruthy();
    }
  });

  it('desde = hasta se rechaza (hasta es exclusivo)', () => {
    const r = validarFiltros(editados({ desde: '2026-11-01T10:00', hasta: '2026-11-01T10:00' }));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errores.hasta).toContain('posterior');
  });

  it('desde > hasta se rechaza', () => {
    const r = validarFiltros(editados({ desde: '2026-11-02T00:00', hasta: '2026-11-01T00:00' }));
    expect(r.ok).toBe(false);
  });

  it('magnitudes: número finito entre −10 y 10, con coma o punto', () => {
    const r = validarFiltros(editados({ magnitudMin: '4,5', magnitudMax: '-1' }));
    expect(r.ok).toBe(false); // min > max
    const ok = validarFiltros(editados({ magnitudMin: '4,5', magnitudMax: '7' }));
    expect(ok).toEqual({ ok: true, filtros: { magnitudMin: 4.5, magnitudMax: 7 } });
  });

  it('rechaza magnitudes fuera de rango, notación científica y texto', () => {
    for (const magnitudMin of ['11', '-10.5', '1e3', 'abc', 'Infinity', '--1']) {
      const r = validarFiltros(editados({ magnitudMin }));
      expect(r.ok, magnitudMin).toBe(false);
      if (!r.ok) expect(r.errores.magnitudMin).toBeTruthy();
    }
  });

  it('magnitud mín. = máx. es válida (comparación inclusiva)', () => {
    const r = validarFiltros(editados({ magnitudMin: '5', magnitudMax: '5' }));
    expect(r.ok).toBe(true);
  });

  it('mín > máx se rechaza junto al campo máximo', () => {
    const r = validarFiltros(editados({ magnitudMin: '6', magnitudMax: '5' }));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errores.magnitudMax).toBeTruthy();
  });

  it('país: ADM0_A3 o «Sin país asignado» literal', () => {
    expect(validarFiltros(editados({ pais: 'USA' }))).toEqual({ ok: true, filtros: { pais: 'USA' } });
    expect(validarFiltros(editados({ pais: SIN_PAIS }))).toEqual({
      ok: true,
      filtros: { pais: SIN_PAIS },
    });
    expect(validarFiltros(editados({ pais: 'usa' })).ok).toBe(false);
    expect(validarFiltros(editados({ pais: 'Chile' })).ok).toBe(false);
  });

  it('subregión: hasta 80 caracteres', () => {
    expect(validarFiltros(editados({ subregion: 'x'.repeat(80) })).ok).toBe(true);
    expect(validarFiltros(editados({ subregion: 'x'.repeat(81) })).ok).toBe(false);
  });

  it('recorta espacios y trata «solo espacios» como vacío', () => {
    expect(validarFiltros(editados({ subregion: '  Southern Asia ', pais: '   ' }))).toEqual({
      ok: true,
      filtros: { subregion: 'Southern Asia' },
    });
  });

  it('acumula los errores de varios campos', () => {
    const r = validarFiltros(editados({ desde: 'x', magnitudMin: 'y' }));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(Object.keys(r.errores).sort()).toEqual(['desde', 'magnitudMin']);
  });
});

describe('aQuery', () => {
  const todos: FiltrosAplicados = {
    desde: '2026-11-01T10:30:00.000Z',
    hasta: '2026-11-02T00:00:00.000Z',
    magnitudMin: 4,
    magnitudMax: 7.5,
    pais: SIN_PAIS,
    subregion: 'Northern America',
  };

  it('completo: todos los filtros, con Z y sin sinteticos', () => {
    const q = new URLSearchParams(aQuery(todos, 'completo'));
    expect(q.get('desde')).toBe('2026-11-01T10:30:00.000Z');
    expect(q.get('hasta')).toBe('2026-11-02T00:00:00.000Z');
    expect(q.get('magnitud_min')).toBe('4');
    expect(q.get('magnitud_max')).toBe('7.5');
    expect(q.get('pais')).toBe('Sin país asignado');
    expect(q.get('subregion')).toBe('Northern America');
    expect(aQuery(todos, 'completo')).not.toContain('sinteticos');
  });

  it('omite los vacíos y devuelve cadena vacía sin filtros', () => {
    expect(aQuery({}, 'completo')).toBe('');
    expect(aQuery({ magnitudMin: 0 }, 'completo')).toBe('magnitud_min=0');
  });

  it('comparación: solo magnitud y país/subregión, nunca fechas', () => {
    const q = new URLSearchParams(aQuery(todos, 'comparacion'));
    expect([...q.keys()].sort()).toEqual(['magnitud_max', 'magnitud_min', 'pais', 'subregion']);
  });

  it('extra: añade limite y desplazamiento al final', () => {
    const q = aQuery({ magnitudMin: 2 }, 'completo', { limite: 50, desplazamiento: 50 });
    expect(q).toBe('magnitud_min=2&limite=50&desplazamiento=50');
  });

  it('hora: acota a 31 días un rango de 40 días', () => {
    const ahora = Date.parse('2026-11-02T12:00:00.000Z');
    const q = new URLSearchParams(
      aQuery(
        { desde: '2026-09-20T00:00:00.000Z', hasta: '2026-10-30T00:00:00.000Z' },
        'hora',
        undefined,
        ahora,
      ),
    );
    expect(q.get('hasta')).toBe('2026-10-30T00:00:00.000Z');
    expect(q.get('desde')).toBe('2026-09-29T00:00:00.000Z');
  });
});

describe('aQuery con vista (modo y sintéticos, 007)', () => {
  const ahora = Date.parse('2026-11-02T12:00:00.000Z');
  const replay: VistaDatos = { modo: 'replay', sinteticos: false };
  const sinteticos: VistaDatos = { modo: 'live', sinteticos: true };
  const ambos: VistaDatos = { modo: 'replay', sinteticos: true };
  const f: FiltrosAplicados = { magnitudMin: 4, pais: 'CHL' };

  it('la vista por defecto es en directo y sin sintéticos', () => {
    expect(VISTA_VIVO).toEqual({ modo: 'live', sinteticos: false });
  });

  it('por defecto la query no cambia: ni `modo` ni `incluir_sinteticos`', () => {
    for (const modo of ['completo', 'hora', 'comparacion'] as const) {
      const sin = aQuery(f, modo, {}, ahora);
      expect(aQuery(f, modo, {}, ahora, VISTA_VIVO)).toBe(sin);
      expect(sin).not.toContain('modo');
      expect(sin).not.toContain('sinteticos');
    }
    expect(aQuery({}, 'completo')).toBe('');
  });

  it('replay añade `modo=replay`', () => {
    const q = new URLSearchParams(aQuery(f, 'completo', {}, ahora, replay));
    expect(q.get('modo')).toBe('replay');
    expect(q.has('incluir_sinteticos')).toBe(false);
    expect(q.get('magnitud_min')).toBe('4');
  });

  it('sintéticos añade `incluir_sinteticos=true` y no `modo`', () => {
    const q = new URLSearchParams(aQuery(f, 'completo', {}, ahora, sinteticos));
    expect(q.get('incluir_sinteticos')).toBe('true');
    expect(q.has('modo')).toBe(false);
  });

  it('también llega a la ventana horaria, con su acotado', () => {
    const q = new URLSearchParams(
      aQuery({ desde: '2026-08-01T00:00:00.000Z' }, 'hora', {}, ahora, ambos),
    );
    expect(q.get('modo')).toBe('replay');
    expect(q.get('incluir_sinteticos')).toBe('true');
    expect(q.get('desde')).toBe('2026-10-02T12:00:00.000Z');
  });

  it('la comparación no lleva ni `modo` ni `incluir_sinteticos`, sea cual sea la vista', () => {
    for (const vista of [replay, sinteticos, ambos]) {
      const q = new URLSearchParams(aQuery({ ...f, desde: '2026-11-01T00:00:00.000Z' }, 'comparacion', {}, ahora, vista));
      expect([...q.keys()].sort()).toEqual(['magnitud_min', 'pais']);
    }
  });

  it('la vista va antes de `extra` (la paginación sigue al final)', () => {
    const q = aQuery({ magnitudMin: 2 }, 'completo', { limite: 50, desplazamiento: 0 }, ahora, ambos);
    expect(q).toBe('magnitud_min=2&modo=replay&incluir_sinteticos=true&limite=50&desplazamiento=0');
  });
});

describe('notaOrigenDatos', () => {
  it('en directo sin sintéticos: solo eventos reales', () => {
    expect(notaOrigenDatos(VISTA_VIVO)).toBe('Solo se muestran eventos reales.');
  });

  it('con sintéticos: lo dice y los marca', () => {
    const t = notaOrigenDatos({ modo: 'live', sinteticos: true });
    expect(t).toContain('casos de prueba sintéticos');
    expect(t).not.toContain('Solo se muestran eventos reales');
  });

  it('en reproducción: no son datos en directo', () => {
    const t = notaOrigenDatos({ modo: 'replay', sinteticos: false });
    expect(t).toContain('REPRODUCCIÓN');
    expect(t).toContain('no son datos en directo');
    expect(t).not.toContain('sintéticos');
  });

  it('en reproducción con sintéticos: ambas cosas', () => {
    const t = notaOrigenDatos({ modo: 'replay', sinteticos: true });
    expect(t).toContain('REPRODUCCIÓN');
    expect(t).toContain('sintéticos');
  });
});

describe('acotarVentanaHora', () => {
  const ahora = Date.parse('2026-11-02T12:00:00.000Z');

  it('rango de exactamente 31 días: no se toca', () => {
    const hasta = '2026-10-31T00:00:00.000Z';
    const desde = new Date(Date.parse(hasta) - 31 * DIA).toISOString();
    expect(acotarVentanaHora({ desde, hasta }, ahora)).toEqual({
      filtros: { desde, hasta },
      acotado: false,
    });
  });

  it('rango de 40 días con hasta: los últimos 31 hasta `hasta`', () => {
    const r = acotarVentanaHora(
      { desde: '2026-09-20T00:00:00.000Z', hasta: '2026-10-30T00:00:00.000Z' },
      ahora,
    );
    expect(r.acotado).toBe(true);
    expect(r.filtros.desde).toBe('2026-09-29T00:00:00.000Z');
    expect(r.filtros.hasta).toBe('2026-10-30T00:00:00.000Z');
  });

  it('solo desde antiguo: hasta pasa a ser ahora', () => {
    const r = acotarVentanaHora({ desde: '2026-08-01T00:00:00.000Z' }, ahora);
    expect(r.acotado).toBe(true);
    expect(r.filtros.hasta).toBe('2026-11-02T12:00:00.000Z');
    expect(r.filtros.desde).toBe('2026-10-02T12:00:00.000Z');
  });

  it('sin fechas o solo hasta: no se toca (la API usa 24 h)', () => {
    expect(acotarVentanaHora({}, ahora)).toEqual({ filtros: {}, acotado: false });
    const f = { hasta: '2026-10-01T00:00:00.000Z' };
    expect(acotarVentanaHora(f, ahora)).toEqual({ filtros: f, acotado: false });
  });

  it('conserva el resto de filtros', () => {
    const r = acotarVentanaHora(
      { desde: '2026-08-01T00:00:00.000Z', magnitudMin: 4, pais: 'CHL' },
      ahora,
    );
    expect(r.filtros.magnitudMin).toBe(4);
    expect(r.filtros.pais).toBe('CHL');
  });
});
