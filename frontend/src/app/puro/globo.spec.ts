import { EventoMapa } from '../modelos/api';
import { COLOR_ND, estiloCirculo } from './escalas';
import {
  ANILLOS_MAX,
  anillosGlobo,
  colorAnillo,
  colorPulso,
  escaparHtml,
  etiquetaGlobo,
  puntosGlobo,
  RADIO_ANILLO_MAX,
  RADIO_ANILLO_MIN,
} from './globo';

function evento(id: string, extra: Partial<EventoMapa['properties']> = {}, coords: [number, number] = [-122, 38]): EventoMapa {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: coords },
    properties: {
      event_id: id,
      ocurrencia: '2026-11-08T10:00:00.000Z',
      updated: '2026-11-08T10:05:00.000Z',
      magnitud: 4.5,
      profundidad: 10,
      pais_nombre: 'México',
      sintetico: false,
      reproducido_en: null,
      ...extra,
    },
  };
}

describe('escaparHtml', () => {
  it('neutraliza los caracteres de HTML', () => {
    expect(escaparHtml(`<img src=x onerror="a('b')">&`)).toBe(
      '&lt;img src=x onerror=&quot;a(&#39;b&#39;)&quot;&gt;&amp;',
    );
  });
});

describe('puntosGlobo', () => {
  it('usa [lon, lat] de GeoJSON, el color de profundidad del mapa plano y crece con la magnitud', () => {
    const [p] = puntosGlobo([evento('a', {}, [140, 35])]);
    expect(p.lat).toBe(35);
    expect(p.lng).toBe(140);
    expect(p.color).toBe(estiloCirculo(4.5, 10).color);
    const [grande] = puntosGlobo([evento('b', { magnitud: 7 })]);
    expect(grande.altura).toBeGreaterThan(p.altura);
    expect(grande.radio).toBeGreaterThan(p.radio);
  });

  it('sin magnitud ni profundidad: gris ND y tamaño mínimo, nunca como 0 con color', () => {
    const [p] = puntosGlobo([evento('a', { magnitud: null, profundidad: null })]);
    expect(p.color).toBe(COLOR_ND);
    const [cero] = puntosGlobo([evento('b', { magnitud: 0 })]);
    expect(p.radio).toBeLessThanOrEqual(cero.radio);
  });

  it('descarta coordenadas no finitas', () => {
    expect(puntosGlobo([evento('a', {}, [Number.NaN, 10])])).toHaveLength(0);
  });
});

describe('anillosGlobo', () => {
  it('solo los más recientes, como máximo ANILLOS_MAX, del más nuevo al más viejo', () => {
    const muchos = Array.from({ length: ANILLOS_MAX + 15 }, (_, i) =>
      evento(`e${i}`, { ocurrencia: new Date(Date.UTC(2026, 10, 1, 0, i)).toISOString() }),
    );
    const anillos = anillosGlobo(muchos);
    expect(anillos).toHaveLength(ANILLOS_MAX);
    expect(anillos[0].id).toBe(`e${ANILLOS_MAX + 14}`);
  });

  it('el radio máximo crece con la magnitud y queda acotado', () => {
    const [m2] = anillosGlobo([evento('a', { magnitud: 2 })]);
    const [m6] = anillosGlobo([evento('b', { magnitud: 6 })]);
    const [m9] = anillosGlobo([evento('c', { magnitud: 9.5 })]);
    expect(m6.radioMax).toBeGreaterThan(m2.radioMax);
    expect(m9.radioMax).toBe(RADIO_ANILLO_MAX);
    const [nd] = anillosGlobo([evento('d', { magnitud: null })]);
    expect(nd.radioMax).toBe(RADIO_ANILLO_MIN);
  });

  it('con movimiento reducido no hay pulsaciones', () => {
    expect(anillosGlobo([evento('a')], { movimientoReducido: true })).toEqual([]);
  });
});

describe('colorPulso', () => {
  it('sube de ámbar a rojo con la magnitud y deja ND en gris', () => {
    expect(colorPulso(2)).toBe('#ffb347');
    expect(colorPulso(4.5)).toBe('#ff6b3d');
    expect(colorPulso(6.1)).toBe('#ff2e4d');
    expect(colorPulso(null)).toBe('#c8d0d8');
    expect(anillosGlobo([evento('a', { magnitud: 6.5 })])[0].color).toBe('#ff2e4d');
  });
});

describe('colorAnillo', () => {
  it('se desvanece de opaco a transparente a lo largo del anillo', () => {
    const f = colorAnillo('#ffffb2');
    expect(f(0)).toBe('rgba(255, 255, 178, 1)');
    expect(f(1)).toBe('rgba(255, 255, 178, 0)');
  });
});

describe('etiquetaGlobo', () => {
  it('magnitud, lugar y hora UTC, con el texto de la API escapado', () => {
    const html = etiquetaGlobo(evento('a', { pais_nombre: '<b>x</b>' }).properties);
    expect(html).toContain('M 4,5');
    expect(html).toContain('&lt;b&gt;x&lt;/b&gt;');
    expect(html).not.toContain('<b>x</b>');
    expect(html).toContain('08/11/2026 10:00:00 UTC');
  });

  it('marca los casos sintéticos y explica «Sin país asignado»', () => {
    const html = etiquetaGlobo(evento('a', { sintetico: true, pais_nombre: 'Sin país asignado' }).properties);
    expect(html).toContain('SINTÉTICO');
    expect(html).toContain('mar o fuera de fronteras');
  });
});
