import { crearTraductor } from '../i18n/traducir';
import {
  ND,
  formatearDecimal,
  formatearEntero,
  formatearHoraConUtc,
  formatearInstanteUtc,
  formatearMagnitud,
  formatearPorcentaje,
  formatearProfundidad,
} from './formato';

describe('números', () => {
  it('porcentaje con un decimal fijo, para que una columna de cuotas quede alineada', () => {
    expect(formatearPorcentaje(74)).toBe('74,0 %');
    expect(formatearPorcentaje(20.34)).toBe('20,3 %');
    expect(formatearPorcentaje(0)).toBe('0,0 %');
    expect(formatearPorcentaje(null)).toBe('ND');
    expect(formatearPorcentaje(74, crearTraductor('en'))).toBe('74.0%');
  });
  it('null y no finitos → «ND», nunca 0', () => {
    expect(ND).toBe('ND');
    expect(formatearEntero(null)).toBe('ND');
    expect(formatearDecimal(null, 2)).toBe('ND');
    expect(formatearDecimal(Number.NaN, 1)).toBe('ND');
    expect(formatearMagnitud(null)).toBe('ND');
    expect(formatearProfundidad(null)).toBe('ND');
  });

  it('el cero real se muestra como 0, no como ND', () => {
    expect(formatearEntero(0)).toBe('0');
    expect(formatearMagnitud(0)).toBe('0,0');
  });

  it('coma decimal y separador de miles en español', () => {
    expect(formatearDecimal(4.5, 1)).toBe('4,5');
    expect(formatearEntero(18302)).toBe('18.302');
    expect(formatearEntero(254)).toBe('254');
    expect(formatearDecimal(50.1425, 2)).toBe('50,14');
  });

  it('el cociente conserva hasta 2 decimales sin ceros sobrantes', () => {
    expect(formatearDecimal(0.6, 2)).toBe('0,6');
    expect(formatearDecimal(1, 2)).toBe('1');
  });

  it('magnitud con 1 decimal; profundidad con km, también negativa', () => {
    expect(formatearMagnitud(2.14)).toBe('2,1');
    expect(formatearProfundidad(30.52)).toBe('30,5 km');
    expect(formatearProfundidad(-1.2)).toBe('-1,2 km');
  });
});

describe('fechas', () => {
  it('instante UTC con día/mes/año y sufijo UTC', () => {
    expect(formatearInstanteUtc('2026-11-02T15:41:58.430Z')).toBe('02/11/2026 15:41:58 UTC');
  });

  it('instante ausente → ND; inválido → ND', () => {
    expect(formatearInstanteUtc(null)).toBe('ND');
    expect(formatearInstanteUtc('no es fecha')).toBe('ND');
  });

  it('hora local con la hora UTC entre paréntesis', () => {
    expect(formatearHoraConUtc('2026-11-02T13:03:28.431Z', 'Europe/Madrid')).toBe(
      '14:03:28 (13:03 UTC)',
    );
  });

  it('hora local en verano: desfase de 2 h', () => {
    expect(formatearHoraConUtc('2026-07-01T13:03:28.000Z', 'Europe/Madrid')).toBe(
      '15:03:28 (13:03 UTC)',
    );
  });

  it('hora con UTC: null → ND', () => {
    expect(formatearHoraConUtc(null, 'Europe/Madrid')).toBe('ND');
  });
});
