import { TestBed } from '@angular/core/testing';
import { ConfigService, validarUrlBase } from './config.service';

describe('validarUrlBase', () => {
  it('acepta HTTPS (ngrok)', () => {
    expect(validarUrlBase('https://abc-123.ngrok-free.app')).toEqual({
      ok: true,
      url: 'https://abc-123.ngrok-free.app',
    });
  });

  it('acepta http solo en 127.0.0.1 y localhost', () => {
    expect(validarUrlBase('http://127.0.0.1:8000').ok).toBe(true);
    expect(validarUrlBase('http://localhost:8000').ok).toBe(true);
  });

  it('rechaza http en cualquier otro host', () => {
    const r = validarUrlBase('http://ejemplo.com');
    expect(r.ok).toBe(false);
  });

  it('quita la barra final', () => {
    expect(validarUrlBase('https://api.ejemplo.dev/')).toEqual({
      ok: true,
      url: 'https://api.ejemplo.dev',
    });
    expect(validarUrlBase('http://127.0.0.1:8000///')).toEqual({
      ok: true,
      url: 'http://127.0.0.1:8000',
    });
  });

  it('rechaza lo que no es una URL, otros esquemas, rutas, consulta y credenciales', () => {
    for (const v of [
      '',
      '   ',
      'api.ejemplo.dev',
      'ftp://api.ejemplo.dev',
      'https://api.ejemplo.dev/v1',
      'https://api.ejemplo.dev?x=1',
      'https://usuario:clave@api.ejemplo.dev',
      42,
      null,
      undefined,
    ]) {
      expect(validarUrlBase(v).ok, String(v)).toBe(false);
    }
  });

  it('rechaza el marcador de config.ejemplo.json sin sustituir', () => {
    expect(validarUrlBase('https://SUBDOMINIO.ngrok-free.app').ok).toBe(false);
  });
});

describe('ConfigService', () => {
  function crear(respuesta: Partial<Response> | Error) {
    const fetchFalso = vi.fn(async () => {
      if (respuesta instanceof Error) throw respuesta;
      return respuesta as Response;
    });
    vi.stubGlobal('fetch', fetchFalso);
    return { servicio: TestBed.inject(ConfigService), fetchFalso };
  }

  afterEach(() => vi.unstubAllGlobals());

  it('lee config.json sin caché y expone la URL', async () => {
    const { servicio, fetchFalso } = crear({
      ok: true,
      json: async () => ({ apiBaseUrl: 'http://127.0.0.1:8000/' }),
    });
    await servicio.cargar();
    expect(fetchFalso).toHaveBeenCalledWith('config.json', { cache: 'no-store' });
    expect(servicio.apiBaseUrl()).toBe('http://127.0.0.1:8000');
    expect(servicio.error()).toBeNull();
  });

  it('cuerpo sin apiBaseUrl → error de configuración, sin lanzar', async () => {
    const { servicio } = crear({ ok: true, json: async () => ({ otra: 1 }) });
    await servicio.cargar();
    expect(servicio.apiBaseUrl()).toBeNull();
    expect(servicio.error()).toContain('apiBaseUrl');
  });

  it('fichero ausente (404) → error', async () => {
    const { servicio } = crear({ ok: false, status: 404 });
    await servicio.cargar();
    expect(servicio.apiBaseUrl()).toBeNull();
    expect(servicio.error()).toBeTruthy();
  });

  it('JSON roto o fallo de red → error', async () => {
    const roto = crear({
      ok: true,
      json: async () => {
        throw new SyntaxError('x');
      },
    });
    await roto.servicio.cargar();
    expect(roto.servicio.error()).toBeTruthy();
  });

  it('URL no válida → error con el motivo', async () => {
    const { servicio } = crear({ ok: true, json: async () => ({ apiBaseUrl: 'http://ejemplo.com' }) });
    await servicio.cargar();
    expect(servicio.apiBaseUrl()).toBeNull();
    expect(servicio.error()).toContain('HTTPS');
  });
});
