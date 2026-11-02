import { etiquetaDatosAntiguos } from './etiqueta-antiguos';

describe('etiquetaDatosAntiguos', () => {
  it('muestra la hora de la última lectura correcta con su equivalente UTC', () => {
    const ms = Date.UTC(2026, 10, 2, 13, 3, 28);
    expect(etiquetaDatosAntiguos(ms, 'Europe/Madrid')).toBe(
      'datos del 14:03:28 (13:03 UTC), desactualizados',
    );
  });

  it('sin hora de lectura dice «ND», no una hora inventada', () => {
    expect(etiquetaDatosAntiguos(null)).toBe('datos de ND, desactualizados');
  });
});
