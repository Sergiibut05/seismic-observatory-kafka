import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { cabecerasInterceptor } from './nucleo/cabeceras.interceptor';
import { ConfigService } from './nucleo/config.service';

async function montar(apiBaseUrl: string) {
  vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({ apiBaseUrl }) }));
  TestBed.configureTestingModule({
    imports: [App],
    providers: [
      provideHttpClient(withInterceptors([cabecerasInterceptor])),
      provideHttpClientTesting(),
    ],
  });
  await TestBed.inject(ConfigService).cargar();
  const fixture = TestBed.createComponent(App);
  await fixture.whenStable();
  return { fixture, http: TestBed.inject(HttpTestingController), el: fixture.nativeElement as HTMLElement };
}

describe('App (esqueleto)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('coloca todos los componentes y el enlace de salto', async () => {
    const { el } = await montar('http://127.0.0.1:8000');
    for (const sel of [
      'app-estado',
      'app-filtros',
      'app-mapa',
      'app-tabla',
      'app-recuentos',
      'app-distribuciones',
      'app-comparacion',
      'app-nota-aviso',
    ]) {
      expect(el.querySelector(sel), sel).not.toBeNull();
    }
    expect(el.querySelector('a.saltar')?.getAttribute('href')).toBe('#contenido');
    expect(el.querySelector('main#contenido')).not.toBeNull();
    expect(el.querySelector('h1')?.textContent).toContain('Observatorio');
  });

  it('con la configuración válida arranca la ronda de peticiones (9 + 2 de opciones)', async () => {
    const { http } = await montar('http://127.0.0.1:8000');
    expect(http.match(() => true).length).toBe(11);
  });

  it('con la configuración inválida muestra el error y no pide nada', async () => {
    const { el, http } = await montar('http://ejemplo.com');
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('HTTPS');
    expect(el.querySelector('app-estado')).toBeNull();
    expect(http.match(() => true).length).toBe(0);
  });
});
