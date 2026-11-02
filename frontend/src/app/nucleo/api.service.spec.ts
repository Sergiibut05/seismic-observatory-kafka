import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { clasificarError } from '../puro/errores';
import { ApiService } from './api.service';
import { cabecerasInterceptor } from './cabeceras.interceptor';
import { ConfigService } from './config.service';

async function preparar(base: string | null = 'http://127.0.0.1:8000') {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptors([cabecerasInterceptor])),
      provideHttpClientTesting(),
    ],
  });
  const config = TestBed.inject(ConfigService);
  if (base) {
    vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({ apiBaseUrl: base }) }));
    await config.cargar();
  }
  return {
    api: TestBed.inject(ApiService),
    http: TestBed.inject(HttpTestingController),
  };
}

describe('ApiService + cabeceras.interceptor', () => {
  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
    vi.unstubAllGlobals();
  });

  it('cada endpoint es un GET con la cabecera ngrok y la base de la configuración', async () => {
    const { api, http } = await preparar();
    const llamadas: [() => unknown, string][] = [
      [() => api.status(), '/status'],
      [() => api.eventos('limite=50'), '/eventos?limite=50'],
      [() => api.eventosMapa(), '/eventos/mapa'],
      [() => api.recuentosPais(), '/recuentos/pais'],
      [() => api.recuentosSubregion(), '/recuentos/subregion'],
      [() => api.recuentosHora(), '/recuentos/hora'],
      [() => api.distribucionMagnitud(), '/distribuciones/magnitud'],
      [() => api.distribucionProfundidad(), '/distribuciones/profundidad'],
      [() => api.comparacionHistorica('magnitud_min=5'), '/comparacion-historica?magnitud_min=5'],
    ];
    for (const [llamar, ruta] of llamadas) {
      (llamar() as { subscribe: () => void }).subscribe();
      const req = http.expectOne(`http://127.0.0.1:8000${ruta}`);
      expect(req.request.method).toBe('GET');
      expect(req.request.headers.get('ngrok-skip-browser-warning')).toBe('1');
      req.flush({});
    }
  });

  it('un POST (u otro método) falla sin salir a la red', async () => {
    await preparar();
    const http = TestBed.inject(HttpClient);
    for (const metodo of ['POST', 'PUT', 'DELETE', 'PATCH'] as const) {
      const error = await firstValueFrom(http.request(metodo, 'http://127.0.0.1:8000/status')).catch(
        (e: unknown) => e,
      );
      expect(clasificarError(error).tipo).toBe('metodo_no_permitido');
    }
    // `verify()` en afterEach comprueba que no se envió ninguna petición.
  });

  it('con la configuración inválida no hay peticiones y el error es de configuración', async () => {
    const { api } = await preparar(null);
    const error = await firstValueFrom(api.status()).catch((e: unknown) => e);
    expect(clasificarError(error).tipo).toBe('configuracion');
  });

  it('un 200 con HTML se clasifica como respuesta no válida', async () => {
    const { api, http } = await preparar();
    const promesa = firstValueFrom(api.status()).catch((e: unknown) => e);
    http.expectOne('http://127.0.0.1:8000/status').flush('<html>aviso de ngrok</html>', {
      status: 200,
      statusText: 'OK',
    });
    expect(clasificarError(await promesa).tipo).toBe('respuesta_invalida');
  });

  it('un 503 llega clasificado como servicio no disponible', async () => {
    const { api, http } = await preparar();
    const promesa = firstValueFrom(api.eventos()).catch((e: unknown) => e);
    http
      .expectOne('http://127.0.0.1:8000/eventos')
      .flush({ error: 'servicio_no_disponible' }, { status: 503, statusText: 'Service Unavailable' });
    expect(clasificarError(await promesa).tipo).toBe('servicio_no_disponible');
  });
});
