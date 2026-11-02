import { clasificarError } from './errores';

describe('clasificarError', () => {
  it('400 con parámetro: nombra el parámetro y no repite texto interno', () => {
    const e = clasificarError({
      status: 400,
      error: { error: 'parametro_invalido', parametro: 'magnitud_min' },
    });
    expect(e.tipo).toBe('parametro_invalido');
    expect(e.status).toBe(400);
    expect(e.parametro).toBe('magnitud_min');
    expect(e.motivo).toContain('magnitud_min');
  });

  it('400 sin cuerpo reconocible: motivo genérico', () => {
    const e = clasificarError({ status: 400, error: 'cualquier cosa' });
    expect(e.tipo).toBe('parametro_invalido');
    expect(e.parametro).toBeNull();
  });

  it('503: servicio no disponible', () => {
    const e = clasificarError({ status: 503, error: { error: 'servicio_no_disponible' } });
    expect(e.tipo).toBe('servicio_no_disponible');
    expect(e.motivo).toMatch(/base de datos|no disponible/i);
  });

  it('500: error interno sin filtrar el texto del cuerpo', () => {
    const e = clasificarError({ status: 500, error: { error: 'error_interno', traza: 'SECRETO' } });
    expect(e.tipo).toBe('error_interno');
    expect(e.motivo).not.toContain('SECRETO');
  });

  it('estado 0: sin respuesta (red, túnel o CORS)', () => {
    const e = clasificarError({ status: 0, error: new ProgressEvent('error') });
    expect(e.tipo).toBe('red');
    expect(e.status).toBe(0);
    expect(e.motivo).toContain('CORS');
  });

  it('200 con HTML (página de aviso de ngrok): respuesta_invalida', () => {
    const e = clasificarError({
      status: 200,
      ok: false,
      error: { error: new SyntaxError('Unexpected token <'), text: '<html>aviso</html>' },
    });
    expect(e.tipo).toBe('respuesta_invalida');
    expect(e.motivo).not.toContain('<html>');
  });

  it('otro estado HTTP (404, 405): http con el código', () => {
    const e = clasificarError({ status: 405, error: null });
    expect(e.tipo).toBe('http');
    expect(e.motivo).toContain('405');
  });

  it('método no permitido por el interceptor', () => {
    const e = clasificarError({ tipo: 'metodo_no_permitido', metodo: 'POST' });
    expect(e.tipo).toBe('metodo_no_permitido');
  });

  it('error de configuración', () => {
    const e = clasificarError({ tipo: 'configuracion' });
    expect(e.tipo).toBe('configuracion');
  });

  it('un valor desconocido se clasifica sin lanzar y sin filtrar su texto', () => {
    const e = clasificarError(new Error('cadena de conexión postgres://x'));
    expect(e.tipo).toBe('desconocido');
    expect(e.motivo).not.toContain('postgres');
  });
});
