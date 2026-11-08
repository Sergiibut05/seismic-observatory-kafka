import { PropiedadesEventoMapa } from '../../modelos/api';
import { crearFicha, crearResumen } from './mapa-ficha';

const base: PropiedadesEventoMapa = {
  event_id: 'us7000abcd',
  ocurrencia: '2026-11-02T10:15:30.000Z',
  updated: '2026-11-02T11:00:00.000Z',
  magnitud: 4.5,
  profundidad: 10,
  pais_nombre: 'México',
  sintetico: false,
  reproducido_en: null,
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
    expect(valores.filter((v) => v === 'ND').length).toBe(1);
    expect(ficha.querySelector('.ficha__titulo')?.textContent).toBe('Magnitud ND');
    expect(ficha.textContent).not.toMatch(/0,0|0 km/);
  });

  it('el lugar va bajo el título y «Sin país asignado» explica por qué', () => {
    expect(crearFicha(base).querySelector('.ficha__lugar')?.textContent).toBe('México');
    const mar = crearFicha({ ...base, pais_nombre: 'Sin país asignado' });
    expect(mar.querySelector('.ficha__lugar')?.textContent).toContain('mar o fuera de fronteras');
  });

  it('el resumen al pasar el ratón es una línea de texto con magnitud y lugar', () => {
    expect(crearResumen(base).textContent).toBe('M 4,5, México');
    expect(crearResumen({ ...base, pais_nombre: 'Sin país asignado', magnitud: null }).textContent).toBe(
      'M ND, sin país asignado',
    );
    const xss = crearResumen({ ...base, pais_nombre: '<b>x</b>' });
    expect(xss.querySelector('b')).toBeNull();
  });

  it('no interpreta como HTML el texto que viene de la API', () => {
    const ficha = crearFicha({ ...base, pais_nombre: '<img src=x onerror=alert(1)>' });
    expect(ficha.querySelector('img')).toBeNull();
    expect(ficha.textContent).toContain('<img');
  });

  describe('REPRODUCCIÓN y sintéticos (007)', () => {
    const filas = (p: PropiedadesEventoMapa) =>
      Object.fromEntries(
        Array.from(crearFicha(p).querySelectorAll('dt')).map((dt) => [
          dt.textContent,
          dt.nextElementSibling?.textContent,
        ]),
      );

    it('un evento real en directo no lleva «SINTÉTICO» ni «Reproducido»', () => {
      const ficha = crearFicha(base);
      expect(ficha.textContent).not.toContain('SINTÉTICO');
      expect(ficha.textContent).not.toContain('Reproducido');
      expect(ficha.querySelector('.ficha__marca')).toBeNull();
    });

    it('un sintético muestra la marca «SINTÉTICO» junto al título', () => {
      const ficha = crearFicha({ ...base, event_id: 'synthetic-caso-nuevo', sintetico: true });
      expect(ficha.querySelector('.ficha__marca')?.textContent?.trim()).toBe('SINTÉTICO');
      expect(ficha.querySelector('.ficha__titulo')?.textContent).toContain('SINTÉTICO');
      expect(ficha.getAttribute('aria-label')).toContain('sintético');
    });

    it('en replay muestra «Reproducido» con su hora UTC, además de la ocurrencia original', () => {
      const f = filas({ ...base, reproducido_en: '2026-11-08T13:00:05.000Z' });
      expect(f['Reproducido']).toBe('08/11/2026 13:00:05 UTC');
      expect(f['Ocurrencia']).toBe('02/11/2026 10:15:30 UTC');
    });

    it('sintético en replay: ambas marcas', () => {
      const ficha = crearFicha({
        ...base,
        sintetico: true,
        reproducido_en: '2026-11-08T13:00:05.000Z',
      });
      expect(ficha.textContent).toContain('SINTÉTICO');
      expect(ficha.textContent).toContain('Reproducido');
    });

    it('magnitud nula + sintético: «ND» y «SINTÉTICO», nunca 0', () => {
      const ficha = crearFicha({ ...base, magnitud: null, sintetico: true });
      expect(ficha.querySelector('.ficha__titulo')?.textContent).toContain('ND');
      expect(ficha.textContent).toContain('SINTÉTICO');
      expect(ficha.textContent).not.toMatch(/0,0/);
    });
  });

  it('es un grupo con nombre accesible', () => {
    const ficha = crearFicha(base);
    expect(ficha.getAttribute('role')).toBe('group');
    expect(ficha.getAttribute('aria-label')).toContain('us7000abcd');
  });
});
