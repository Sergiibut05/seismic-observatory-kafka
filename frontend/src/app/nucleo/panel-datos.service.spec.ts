import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { cabecerasInterceptor } from './cabeceras.interceptor';
import { ConfigService } from './config.service';
import { FiltrosStore } from './filtros.store';
import { PanelDatosService, bloqueConDatosAntiguos } from './panel-datos.service';
import { RefrescoService } from './refresco.service';
import { RELOJ } from './reloj';

const BASE = 'http://127.0.0.1:8000';
const RUTAS_RONDA = [
  '/status',
  '/eventos/mapa',
  '/eventos',
  '/recuentos/pais',
  '/recuentos/subregion',
  '/recuentos/hora',
  '/distribuciones/magnitud',
  '/distribuciones/profundidad',
  '/comparacion-historica',
];

let ahora = Date.parse('2026-11-02T16:00:00.000Z');

async function preparar() {
  vi.stubGlobal('fetch', async () => ({ ok: true, json: async () => ({ apiBaseUrl: BASE }) }));
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptors([cabecerasInterceptor])),
      provideHttpClientTesting(),
      { provide: RELOJ, useValue: () => ahora },
    ],
  });
  await TestBed.inject(ConfigService).cargar();
  return {
    http: TestBed.inject(HttpTestingController),
    datos: TestBed.inject(PanelDatosService),
    store: TestBed.inject(FiltrosStore),
  };
}

const ruta = (r: TestRequest) => r.request.url.replace(BASE, '').split('?')[0];

/** Responde a todas las peticiones pendientes con 200 `{}` (salvo las indicadas). */
function responderTodas(http: HttpTestingController, falla: Record<string, number> = {}) {
  const pendientes = http.match(() => true);
  for (const req of pendientes) {
    const estado = falla[ruta(req)];
    if (estado) {
      req.flush({ error: 'servicio_no_disponible' }, { status: estado, statusText: 'Error' });
    } else {
      req.flush({ marca: ruta(req) });
    }
  }
  return pendientes;
}

describe('PanelDatosService', () => {
  beforeEach(() => {
    ahora = Date.parse('2026-11-02T16:00:00.000Z');
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    TestBed.inject(HttpTestingController).verify();
  });

  it('una ronda = 9 GET, uno por bloque, con la cabecera de ngrok', async () => {
    const { http, datos } = await preparar();
    const ronda = datos.rondaCompleta();
    const pendientes = http.match(() => true);
    expect(pendientes.map(ruta).sort()).toEqual([...RUTAS_RONDA].sort());
    for (const r of pendientes) {
      expect(r.request.method).toBe('GET');
      expect(r.request.headers.get('ngrok-skip-browser-warning')).toBe('1');
      r.flush({});
    }
    await ronda;
    expect(datos.status().estado).toBe('ok');
    expect(datos.comparacion().lecturaOk).toBe(ahora);
  });

  it('todos los bloques empiezan en «cargando» sin datos', async () => {
    const { datos } = await preparar();
    for (const b of [datos.status(), datos.mapa(), datos.tabla(), datos.porPais, datos.comparacion()]) {
      expect(b).toBeTruthy();
    }
    expect(datos.mapa()).toEqual({ estado: 'cargando', datos: null, lecturaOk: null, error: null });
  });

  it('la ronda aplica los filtros: tabla paginada, comparación sin fechas', async () => {
    const { http, datos, store } = await preparar();
    store.editar({ desde: '2026-11-01T00:00', magnitudMin: '4' });
    store.aplicarYa();
    store.irAPagina(50);
    const ronda = datos.rondaCompleta();
    const pendientes = http.match(() => true);
    const tabla = pendientes.find((r) => ruta(r) === '/eventos')!;
    expect(tabla.request.url).toContain('limite=50');
    expect(tabla.request.url).toContain('desplazamiento=50');
    const comparacion = pendientes.find((r) => ruta(r) === '/comparacion-historica')!;
    expect(comparacion.request.url).toBe(`${BASE}/comparacion-historica?magnitud_min=4`);
    pendientes.forEach((r) => r.flush({}));
    await ronda;
  });

  it('un 503 marca el bloque, conserva los datos y el siguiente 200 lo limpia', async () => {
    const { http, datos } = await preparar();
    let ronda = datos.rondaCompleta();
    responderTodas(http);
    await ronda;
    const anterior = datos.mapa();
    expect(anterior.estado).toBe('ok');

    ahora += 60_000;
    ronda = datos.rondaCompleta();
    responderTodas(http, { '/eventos/mapa': 503 });
    await ronda;
    const fallido = datos.mapa();
    expect(fallido.estado).toBe('error');
    expect(fallido.error?.tipo).toBe('servicio_no_disponible');
    expect(fallido.datos).toEqual(anterior.datos);
    expect(fallido.lecturaOk).toBe(anterior.lecturaOk);
    expect(bloqueConDatosAntiguos(fallido)).toBe(true);
    expect(datos.tabla().estado).toBe('ok'); // el resto de bloques no se contagia

    ahora += 60_000;
    ronda = datos.rondaCompleta();
    responderTodas(http);
    await ronda;
    const recuperado = datos.mapa();
    expect(recuperado.estado).toBe('ok');
    expect(recuperado.error).toBeNull();
    expect(recuperado.lecturaOk).toBe(ahora);
  });

  it('si /status falla: aviso «API sin respuesta» y se conserva el último acceso correcto', async () => {
    const { http, datos } = await preparar();
    let ronda = datos.rondaCompleta();
    responderTodas(http);
    await ronda;
    const accesoOk = datos.ultimoAccesoOk();
    expect(datos.estadoSistema().avisos).toEqual([]);

    ahora += 60_000;
    ronda = datos.rondaCompleta();
    for (const r of http.match(() => true)) r.error(new ProgressEvent('error'), { status: 0 });
    await ronda;
    expect(datos.status().error?.tipo).toBe('red');
    expect(datos.estadoSistema().avisos.map((a) => a.codigo)).toEqual(['api_sin_respuesta']);
    expect(datos.ultimoAccesoOk()).toBe(accesoOk);
  });

  it('una petición nueva del mismo bloque cancela la anterior (sin solapes)', async () => {
    const { http, datos } = await preparar();
    const a = datos.cargarTabla();
    const b = datos.cargarTabla();
    await a; // la primera se cancela y resuelve
    const pendientes = http.match(() => true);
    expect(pendientes.filter((r) => !r.cancelled).length).toBe(1);
    pendientes.find((r) => !r.cancelled)!.flush({});
    await b;
  });

  it('rango de 40 días: /recuentos/hora va acotado a 31 y el panel lo anota', async () => {
    const { http, datos, store } = await preparar();
    store.editar({ desde: '2026-09-20T00:00', hasta: '2026-10-30T00:00' });
    store.aplicarYa();
    const ronda = datos.rondaCompleta();
    const pendientes = http.match(() => true);
    const hora = pendientes.find((r) => ruta(r) === '/recuentos/hora')!;
    expect(decodeURIComponent(hora.request.url)).toContain('desde=2026-09-29T00:00:00.000Z');
    expect(datos.horaAcotada()).toEqual({
      desde: '2026-09-29T00:00:00.000Z',
      hasta: '2026-10-30T00:00:00.000Z',
    });
    pendientes.forEach((r) => r.flush({}));
    await ronda;
  });

  it('las opciones de país y subregión se piden sin filtros (2 GET)', async () => {
    const { http, datos, store } = await preparar();
    store.editar({ magnitudMin: '5' });
    store.aplicarYa();
    const p = datos.cargarOpciones();
    const pendientes = http.match(() => true);
    expect(pendientes.map((r) => r.request.url).sort()).toEqual([
      `${BASE}/recuentos/pais`,
      `${BASE}/recuentos/subregion`,
    ]);
    pendientes.forEach((r) => r.flush({ total: 0, categorias: [] }));
    await p;
  });
});

describe('RefrescoService', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    ahora = Date.parse('2026-11-02T16:00:00.000Z');
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete (document as unknown as Record<string, unknown>)['visibilityState'];
    TestBed.inject(HttpTestingController).verify();
  });

  const rutasPendientes = (http: HttpTestingController) => http.match(() => true);

  async function arrancar() {
    const base = await preparar();
    const refresco = TestBed.inject(RefrescoService);
    refresco.iniciar();
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    return { ...base, refresco };
  }

  const fijarVisibilidad = (estado: 'hidden' | 'visible') => {
    Object.defineProperty(document, 'visibilityState', { value: estado, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  };

  it('arranque: 1 ronda (9 GET) + 2 de opciones; luego 1 ronda cada 60 s', async () => {
    const { http } = await arrancar();
    const inicial = rutasPendientes(http);
    expect(inicial.length).toBe(11);
    inicial.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    await vi.advanceTimersByTimeAsync(59_000);
    expect(rutasPendientes(http).length).toBe(0);
    await vi.advanceTimersByTimeAsync(1_000);
    const segunda = rutasPendientes(http);
    expect(segunda.map(ruta).sort()).toEqual([...RUTAS_RONDA].sort());
    segunda.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('un cambio de filtros (tras 400 ms) = exactamente 1 ronda de 9 GET', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.editar({ magnitudMin: '4' });
    store.editar({ magnitudMin: '4,5' });
    await vi.advanceTimersByTimeAsync(399);
    TestBed.tick();
    expect(rutasPendientes(http).length).toBe(0);
    await vi.advanceTimersByTimeAsync(1);
    TestBed.tick();
    const ronda = rutasPendientes(http);
    expect(ronda.length).toBe(9);
    expect(ronda.every((r) => r.request.url.includes('magnitud_min=4.5') || ruta(r) === '/status')).toBe(
      true,
    );
    ronda.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('filtros incoherentes: no se aplican y no hay peticiones', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.editar({ magnitudMin: '7', magnitudMax: '3' });
    await vi.advanceTimersByTimeAsync(1_000);
    TestBed.tick();
    expect(store.hayErrores()).toBe(true);
    expect(store.aplicados()).toEqual({});
    expect(rutasPendientes(http).length).toBe(0);
  });

  it('cambiar de página recarga solo la tabla', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.irAPagina(50);
    TestBed.tick();
    const pendientes = rutasPendientes(http);
    expect(pendientes.length).toBe(1);
    expect(pendientes[0].request.url).toContain('desplazamiento=50');
    pendientes[0].flush({});
    await vi.advanceTimersByTimeAsync(0);
  });

  it('pestaña oculta: 0 rondas; al volver, 1 inmediata', async () => {
    const { http } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    fijarVisibilidad('hidden');
    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(rutasPendientes(http).length).toBe(0);

    fijarVisibilidad('visible');
    const ronda = rutasPendientes(http);
    expect(ronda.map(ruta).sort()).toEqual([...RUTAS_RONDA].sort());
    ronda.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });
});
