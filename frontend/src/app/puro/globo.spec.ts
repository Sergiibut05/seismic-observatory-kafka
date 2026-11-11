import { EventoMapa } from '../modelos/api';
import { COLOR_ND, estiloCirculo } from './escalas';
import {
  ALTURA_COLUMNA_ND,
  ANILLOS_MAX,
  anillosGlobo,
  barrasEscena,
  colorAnillo,
  colorPulso,
  escaparHtml,
  etiquetaGlobo,
  alturaColumna,
  instanteCinta,
  marcasCinta,
  paisEnPunto,
  puntosGlobo,
  RADIO_ANILLO_MAX,
  RADIO_ANILLO_MIN,
  recortarPorHora,
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
  it('rojo de pluma: en papel se oscurece con la magnitud, en noche se aclara; ND en gris', () => {
    expect(colorPulso(2)).toBe('#E07A86');
    expect(colorPulso(4.5)).toBe('#C8102E');
    expect(colorPulso(6.1)).toBe('#7A0019');
    expect(colorPulso(null)).toBe('#9A9385');
    expect(colorPulso(6.1, 'noche')).toBe('#FFE3DF');
    expect(colorPulso(null, 'noche')).toBe('#C8D0D8');
    expect(anillosGlobo([evento('a', { magnitud: 6.5 })])[0].color).toBe('#7A0019');
    expect(anillosGlobo([evento('a', { magnitud: 6.5 })], { tema: 'noche' })[0].color).toBe('#FFE3DF');
  });
});

describe('colorAnillo', () => {
  it('se desvanece de opaco a transparente a lo largo del anillo', () => {
    const f = colorAnillo('#ffffb2');
    expect(f(0)).toBe('rgba(255, 255, 178, 1)');
    expect(f(1)).toBe('rgba(255, 255, 178, 0)');
  });
});

describe('alturaColumna', () => {
  it('crece con la magnitud y no trata el nulo como 0', () => {
    expect(alturaColumna(7)).toBeGreaterThan(alturaColumna(2));
    // Visible pero sin tapar la Tierra: M7 no llega a una quinta parte del radio.
    expect(alturaColumna(5)).toBeGreaterThan(alturaColumna(2) * 2);
    expect(alturaColumna(7)).toBeLessThan(0.2);
    expect(alturaColumna(9.5)).toBe(alturaColumna(9));
    expect(alturaColumna(null)).toBe(ALTURA_COLUMNA_ND);
    expect(alturaColumna(null)).not.toBe(alturaColumna(0));
    expect(alturaColumna(null)).toBeLessThan(alturaColumna(0));
  });
});

describe('recortarPorHora', () => {
  it('deja solo lo anterior o igual al corte y no llama a nada más', () => {
    const a = evento('a', { ocurrencia: '2026-11-09T10:00:00.000Z' });
    const b = evento('b', { ocurrencia: '2026-11-09T12:00:00.000Z' });
    const c = evento('c', { ocurrencia: '2026-11-09T14:00:00.000Z' });
    expect(recortarPorHora([a, b, c], '2026-11-09T12:00:00.000Z').map((f) => f.properties.event_id)).toEqual([
      'a',
      'b',
    ]);
    expect(recortarPorHora([a, b, c], null)).toHaveLength(3);
  });
});

describe('marcasCinta', () => {
  it('coloca cada evento en [0, 1] sobre las últimas 24 h', () => {
    const ahora = Date.parse('2026-11-09T18:00:00.000Z');
    const marcas = marcasCinta(
      [
        evento('viejo', { ocurrencia: '2026-11-07T00:00:00.000Z' }),
        evento('nuevo', { ocurrencia: '2026-11-09T18:00:00.000Z' }),
      ],
      ahora,
    );
    const viejo = marcas.find((m) => m.id === 'viejo')!;
    const nuevo = marcas.find((m) => m.id === 'nuevo')!;
    expect(viejo.t).toBe(0);
    expect(nuevo.t).toBe(1);
    expect(instanteCinta(1, ahora, [evento('nuevo', { ocurrencia: '2026-11-09T18:00:00.000Z' })])).toBe(
      '2026-11-09T18:00:00.000Z',
    );
  });
});

describe('paisEnPunto', () => {
  it('devuelve el primer polígono que contiene el punto y null si cae fuera', () => {
    const chile = {
      type: 'Feature' as const,
      properties: { ADM0_A3: 'CHL' },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [
          [
            [-80, -40],
            [-60, -40],
            [-60, -20],
            [-80, -20],
            [-80, -40],
          ],
        ],
      },
    };
    expect(paisEnPunto([chile], -30, -70)?.properties.ADM0_A3).toBe('CHL');
    expect(paisEnPunto([chile], 0, 0)).toBeNull();
  });
});

describe('barrasEscena', () => {
  it('un nulo de magnitud va a «sin valor», nunca al intervalo de 0', () => {
    const barras = barrasEscena(
      [evento('a', { magnitud: null }), evento('b', { magnitud: 0 })],
      'magnitud',
      Date.parse('2026-11-09T12:00:00.000Z'),
    );
    expect(barras.find((b) => b.sinValor)?.valor).toBe(1);
    expect(barras.find((b) => b.etiqueta === '0–1')?.valor).toBe(1);
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
