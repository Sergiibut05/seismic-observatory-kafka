import { PropiedadesEventoMapa } from '../../modelos/api';
import { crearFicha } from './mapa-ficha';

const base: PropiedadesEventoMapa = {
  event_id: 'us7000abcd',
  ocurrencia: '2026-11-02T10:15:30.000Z',
  updated: '2026-11-02T11:00:00.000Z',
  magnitud: 4.5,
  profundidad: 10,
  pais_nombre: 'México',
  sintetico: false,
};

describe('crearFicha', () => {
  it('incluye identificador, tiempos UTC, magnitud, profundidad y país', () => {
    const texto = crearFicha(base).textContent ?? '';
    expect(texto).toContain('us7000abcd');
    expect(texto).toContain('02/11/2026 10:15:30 UTC');
    expect(texto).toContain('02/11/2026 11:00:00 UTC');
    expect(texto).toContain('4,5');
    expect(texto).toContain('10 km');
    expect(texto).toContain('México');
  });

  it('magnitud y profundidad nulas se muestran «ND», nunca 0', () => {
    const ficha = crearFicha({ ...base, magnitud: null, profundidad: null });
    const valores = Array.from(ficha.querySelectorAll('dd')).map((d) => d.textContent);
    expect(valores).toContain('ND');
    expect(valores.filter((v) => v === 'ND').length).toBe(2);
    expect(ficha.textContent).not.toMatch(/0,0|0 km/);
  });

  it('no interpreta como HTML el texto que viene de la API', () => {
    const ficha = crearFicha({ ...base, pais_nombre: '<img src=x onerror=alert(1)>' });
    expect(ficha.querySelector('img')).toBeNull();
    expect(ficha.textContent).toContain('<img');
  });

  it('es un grupo con nombre accesible', () => {
    const ficha = crearFicha(base);
    expect(ficha.getAttribute('role')).toBe('group');
    expect(ficha.getAttribute('aria-label')).toContain('us7000abcd');
  });
});
