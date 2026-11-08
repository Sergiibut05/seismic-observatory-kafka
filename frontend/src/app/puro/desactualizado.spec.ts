import { EstadoApi } from '../modelos/api';
import { UMBRAL_LECTURA_ANTIGUA_MS, calcularEstado, lecturaAntigua } from './desactualizado';

const estado = (parcial: Partial<EstadoApi> = {}): EstadoApi => ({
  base_de_datos: 'conectada',
  eventos_reales: 254,
  eventos_sinteticos: 0,
  eventos_replay: 0,
  ultimo_evento: null,
  ultima_ingesta_correcta: '2026-11-02T16:03:28.431Z',
  periodo_consultado: null,
  datos_desactualizados: false,
  umbral_datos_desactualizados_segundos: 300,
  generated_at: '2026-11-02T16:03:31.832Z',
  ...parcial,
});

const codigos = (r: ReturnType<typeof calcularEstado>) => r.avisos.map((a) => a.codigo);

describe('calcularEstado', () => {
  it('todo en orden: sin avisos', () => {
    expect(calcularEstado(estado(), false).avisos).toEqual([]);
  });

  it('datos_desactualizados = true: aviso', () => {
    const r = calcularEstado(estado({ datos_desactualizados: true }), false);
    expect(codigos(r)).toEqual(['datos_desactualizados']);
  });

  it('datos_desactualizados = null con la base conectada: no inventa aviso', () => {
    expect(calcularEstado(estado({ datos_desactualizados: null }), false).avisos).toEqual([]);
  });

  it('base_de_datos = fallida: aviso propio (y el null no es «desactualizado»)', () => {
    const r = calcularEstado(
      estado({
        base_de_datos: 'fallida',
        datos_desactualizados: null,
        eventos_reales: null,
        ultima_ingesta_correcta: null,
      }),
      false,
    );
    expect(codigos(r)).toEqual(['base_fallida']);
  });

  it('API sin respuesta: aviso aunque la última lectura fuera buena', () => {
    const r = calcularEstado(estado(), true);
    expect(codigos(r)).toEqual(['api_sin_respuesta']);
  });

  it('API sin respuesta y nunca hubo lectura: igualmente un solo aviso', () => {
    expect(codigos(calcularEstado(null, true))).toEqual(['api_sin_respuesta']);
  });

  it('sin lectura todavía y sin fallo: sin avisos (el bloque está cargando)', () => {
    expect(calcularEstado(null, false).avisos).toEqual([]);
  });

  it('desactualizado y base fallida a la vez: dos avisos, en orden de gravedad', () => {
    const r = calcularEstado(
      estado({ base_de_datos: 'fallida', datos_desactualizados: true }),
      false,
    );
    expect(codigos(r)).toEqual(['base_fallida', 'datos_desactualizados']);
  });
});

describe('lecturaAntigua', () => {
  const t0 = Date.parse('2026-11-02T16:00:00.000Z');

  it('59 s no es antigua; 61 s sí', () => {
    expect(lecturaAntigua(t0, t0 + 59_000)).toBe(false);
    expect(lecturaAntigua(t0, t0 + 61_000)).toBe(true);
  });

  it('exactamente 60 s todavía no es antigua', () => {
    expect(UMBRAL_LECTURA_ANTIGUA_MS).toBe(60_000);
    expect(lecturaAntigua(t0, t0 + 60_000)).toBe(false);
  });

  it('sin lectura correcta nunca: antigua', () => {
    expect(lecturaAntigua(null, t0)).toBe(true);
  });

  it('reloj que va hacia atrás: no es antigua', () => {
    expect(lecturaAntigua(t0, t0 - 5_000)).toBe(false);
  });

  it('umbral configurable', () => {
    expect(lecturaAntigua(t0, t0 + 31_000, 30_000)).toBe(true);
  });
});
