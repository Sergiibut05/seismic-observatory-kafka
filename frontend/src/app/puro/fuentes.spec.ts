import { textoFuentes } from './fuentes';

describe('textoFuentes', () => {
  it('siglas en mayúsculas, ordenadas y sin repetir', () => {
    expect(textoFuentes(['usgs', 'emsc'])).toBe('EMSC + USGS');
    expect(textoFuentes(['usgs', 'usgs'])).toBe('USGS');
  });

  it('sin fuentes no inventa nada', () => {
    expect(textoFuentes([])).toBe('');
    expect(textoFuentes(undefined)).toBe('');
    expect(textoFuentes(null)).toBe('');
  });
});
