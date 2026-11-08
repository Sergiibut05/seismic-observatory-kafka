import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { CLAVE_IDIOMA, I18nService } from './i18n/i18n.service';
import { Distribucion } from './modelos/api';
import { cabecerasInterceptor } from './nucleo/cabeceras.interceptor';
import { ConfigService } from './nucleo/config.service';
import { PanelDatosService } from './nucleo/panel-datos.service';

const MAGNITUD: Distribucion = {
  unidad: 'magnitud',
  total: 1234,
  sin_valor: 2,
  intervalos: [
    { desde: 0, hasta: 1, etiqueta: '0–1', recuento: 1200 },
    { desde: 1, hasta: null, etiqueta: '≥ 1', recuento: 32 },
  ],
};

async function montar() {
  vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({ apiBaseUrl: 'http://127.0.0.1:8000' }) }));
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
  const http = TestBed.inject(HttpTestingController);
  // Se descartan las peticiones del arranque: lo que se comprueba es que el cambio de idioma no genera más.
  http.match(() => true);
  TestBed.inject(PanelDatosService).distMagnitud.set({
    estado: 'ok',
    datos: MAGNITUD,
    lecturaOk: Date.parse('2026-11-02T16:00:00Z'),
    error: null,
  });
  await fixture.whenStable();
  return { fixture, http, el: fixture.nativeElement as HTMLElement };
}

const boton = (el: HTMLElement, idioma: string) =>
  el.querySelector<HTMLButtonElement>(`.idioma button[lang="${idioma}"]`)!;

describe('Selector de idioma (AC-2)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    document.documentElement.lang = 'es';
  });

  it('por defecto está en español, con el grupo accesible y ES pulsado', async () => {
    const { el } = await montar();
    expect(el.querySelector('.idioma')?.getAttribute('aria-label')).toBe('Idioma');
    expect(boton(el, 'es').getAttribute('aria-pressed')).toBe('true');
    expect(boton(el, 'en').getAttribute('aria-pressed')).toBe('false');
    expect(el.querySelector('h1')?.textContent).toContain('Observatorio de actividad sísmica');
    expect(document.documentElement.lang).toBe('es');
  });

  it('al pulsar EN cambian la cabecera y un bloque con datos, sin pedir nada a la API', async () => {
    const { fixture, http, el } = await montar();
    const bloque = () => el.querySelector('section[aria-labelledby="titulo-dist-magnitud"]')!;
    expect(bloque().textContent).toContain('1234 eventos; de ellos');
    expect(bloque().textContent).toContain('sin magnitud registrada');

    boton(el, 'en').click();
    await fixture.whenStable();

    expect(el.querySelector('h1')?.textContent).toContain('Seismic activity observatory');
    expect(el.querySelector('a.saltar')?.textContent).toContain('Skip to content');
    expect(el.querySelector('.idioma')?.getAttribute('aria-label')).toBe('Language');
    expect(boton(el, 'en').getAttribute('aria-pressed')).toBe('true');
    expect(boton(el, 'es').getAttribute('aria-pressed')).toBe('false');
    expect(bloque().querySelector('h3')?.textContent).toBe('Magnitude');
    // Números con punto en inglés y los datos de la API (intervalos) intactos.
    expect(bloque().textContent).toContain('1,234 events, of which');
    expect(bloque().textContent).toContain('have no recorded magnitude');
    expect(bloque().querySelector('details summary')?.textContent).toContain('View “Magnitude distribution” as a table');
    expect(bloque().textContent).toContain('0–1');
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem(CLAVE_IDIOMA)).toBe('en');
    expect(http.match(() => true)).toHaveLength(0);

    boton(el, 'es').click();
    await fixture.whenStable();
    expect(el.querySelector('h1')?.textContent).toContain('Observatorio de actividad sísmica');
    expect(document.documentElement.lang).toBe('es');
    expect(http.match(() => true)).toHaveLength(0);
  });

  it('al recargar la aplicación se recupera el idioma elegido', async () => {
    const primera = await montar();
    boton(primera.el, 'en').click();
    await primera.fixture.whenStable();
    TestBed.resetTestingModule();

    const { el } = await montar();
    expect(TestBed.inject(I18nService).idioma()).toBe('en');
    expect(el.querySelector('h1')?.textContent).toContain('Seismic activity observatory');
    expect(boton(el, 'en').getAttribute('aria-pressed')).toBe('true');
    expect(document.documentElement.lang).toBe('en');
  });

  it('la elección de vista (en directo / REPRODUCCIÓN) no cambia: se etiqueta «REPLAY» pero envía lo mismo', async () => {
    const { fixture, el } = await montar();
    boton(el, 'en').click();
    await fixture.whenStable();
    const replay = el.querySelector<HTMLInputElement>('app-vista-datos input[value="replay"]')!;
    expect(replay.value).toBe('replay');
    expect(el.querySelector('label[for="vista-modo-replay"]')?.textContent).toContain('REPLAY');
  });
});
