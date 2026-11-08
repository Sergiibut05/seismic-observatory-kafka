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
      'app-vista-datos',
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

  describe('REPRODUCCIÓN y casos sintéticos (007)', () => {
    /** Cierra la ronda en curso (la cola no lanza otra hasta que acabe) sin inventar datos. */
    async function fallarTodas(http: HttpTestingController, fixture: { whenStable(): Promise<unknown> }) {
      for (const r of http.match(() => true)) {
        r.flush({ error: 'servicio_no_disponible' }, { status: 503, statusText: 'Error' });
      }
      await fixture.whenStable();
    }
    const radio = (el: HTMLElement, valor: string) =>
      el.querySelector<HTMLInputElement>(`app-vista-datos input[type="radio"][value="${valor}"]`)!;
    const interruptor = (el: HTMLElement) =>
      el.querySelector<HTMLInputElement>('app-vista-datos input[role="switch"]')!;

    it('al arrancar: selector en «En directo», interruptor apagado, sin franja ni aviso', async () => {
      const { el, http } = await montar('http://127.0.0.1:8000');
      expect(el.querySelector('app-vista-datos')).not.toBeNull();
      expect(radio(el, 'live').checked).toBe(true);
      expect(interruptor(el).checked).toBe(false);
      expect(el.querySelector('.franja--replay')).toBeNull();
      expect(el.querySelector('.franja--sinteticos')).toBeNull();
      expect(el.querySelector('header')?.textContent).toContain('Eventos reales de USGS');
      // Ninguna petición lleva `modo` ni `incluir_sinteticos`.
      expect(http.match((r) => /modo|sinteticos/.test(r.url)).length).toBe(0);
    });

    it('REPRODUCCIÓN: franja, cabecera rotulada y ninguna petición a /comparacion-historica', async () => {
      const { fixture, el, http } = await montar('http://127.0.0.1:8000');
      await fallarTodas(http, fixture);
      await fixture.whenStable();

      radio(el, 'replay').click();
      await fixture.whenStable();
      expect(el.querySelector('.franja--replay')?.getAttribute('role')).toBe('status');
      expect(el.querySelector('header')?.textContent).toContain('REPRODUCCIÓN');
      expect(el.querySelector('header')?.textContent).not.toContain('Eventos reales de USGS');

      const pendientes = http.match(() => true);
      expect(pendientes.some((r) => r.request.url.includes('/comparacion-historica'))).toBe(false);
      expect(pendientes.filter((r) => r.request.url.includes('modo=replay')).length).toBeGreaterThan(6);
    });

    it('al volver a «En directo» desaparece la franja y vuelve la comparación', async () => {
      const { fixture, el, http } = await montar('http://127.0.0.1:8000');
      await fallarTodas(http, fixture);
      radio(el, 'replay').click();
      await fixture.whenStable();
      await fallarTodas(http, fixture);

      radio(el, 'live').click();
      await fixture.whenStable();
      expect(el.querySelector('.franja--replay')).toBeNull();
      expect(el.querySelector('header')?.textContent).toContain('Eventos reales de USGS');
      const pendientes = http.match(() => true);
      expect(pendientes.some((r) => r.request.url.includes('/comparacion-historica'))).toBe(true);
      expect(pendientes.some((r) => r.request.url.includes('modo'))).toBe(false);
    });

    it('con el interruptor encendido aparece el aviso y las peticiones piden sintéticos', async () => {
      const { fixture, el, http } = await montar('http://127.0.0.1:8000');
      await fallarTodas(http, fixture);
      interruptor(el).click();
      await fixture.whenStable();
      expect(el.querySelector('.franja--sinteticos')?.textContent).toContain('no son terremotos reales');
      const pendientes = http.match(() => true);
      expect(pendientes.filter((r) => r.request.url.includes('incluir_sinteticos=true')).length).toBeGreaterThan(6);
      const comparacion = pendientes.find((r) => r.request.url.includes('/comparacion-historica'))!;
      expect(comparacion.request.url).not.toContain('sinteticos');
    });

    it('con la configuración inválida no hay controles de vista', async () => {
      const { el } = await montar('http://ejemplo.com');
      expect(el.querySelector('app-vista-datos')).toBeNull();
    });
  });

  it('con la configuración inválida muestra el error y no pide nada', async () => {
    const { el, http } = await montar('http://ejemplo.com');
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('HTTPS');
    expect(el.querySelector('app-estado')).toBeNull();
    expect(http.match(() => true).length).toBe(0);
  });
});
