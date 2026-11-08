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

  it('por defecto ninguna petición lleva `modo` ni `incluir_sinteticos`', async () => {
    const { http, datos, store } = await preparar();
    expect(store.vista()).toEqual({ modo: 'live', sinteticos: false });
    const ronda = datos.rondaCompleta();
    const pendientes = http.match(() => true);
    for (const r of pendientes) {
      expect(r.request.url, ruta(r)).not.toContain('modo');
      expect(r.request.url, ruta(r)).not.toContain('sinteticos');
      r.flush({});
    }
    await ronda;
  });

  it('en REPRODUCCIÓN hay 8 GET con `modo=replay` y ninguno a /comparacion-historica', async () => {
    const { http, datos, store } = await preparar();
    store.fijarModo('replay');
    const ronda = datos.rondaCompleta();
    const pendientes = http.match(() => true);
    expect(pendientes.length).toBe(8);
    expect(pendientes.map(ruta).sort()).toEqual(
      RUTAS_RONDA.filter((r) => r !== '/comparacion-historica').sort(),
    );
    for (const r of pendientes) {
      if (ruta(r) === '/status') expect(r.request.url).toBe(`${BASE}/status`);
      else expect(new URL(r.request.url).searchParams.get('modo'), ruta(r)).toBe('replay');
      expect(r.request.method).toBe('GET');
      r.flush({});
    }
    await ronda;
  });

  it('en REPRODUCCIÓN la comparación queda sin pedir y conserva su último estado', async () => {
    const { http, datos, store } = await preparar();
    let ronda = datos.rondaCompleta();
    responderTodas(http);
    await ronda;
    const comparacion = datos.comparacion();
    expect(comparacion.estado).toBe('ok');

    store.fijarModo('replay');
    ronda = datos.rondaCompleta();
    responderTodas(http);
    await ronda;
    expect(datos.comparacion()).toBe(comparacion);
  });

  it('la tabla paginada también lleva `modo=replay`', async () => {
    const { http, datos, store } = await preparar();
    store.fijarModo('replay');
    store.irAPagina(50);
    const p = datos.cargarTabla();
    const [peticion] = http.match(() => true);
    expect(peticion.request.url).toBe(`${BASE}/eventos?modo=replay&limite=50&desplazamiento=50`);
    peticion.flush({});
    await p;
  });

  it('`incluir_sinteticos=true` llega a las 7 peticiones de datos, no a la comparación ni a /status', async () => {
    const { http, datos, store } = await preparar();
    store.fijarSinteticos(true);
    const ronda = datos.rondaCompleta();
    const pendientes = http.match(() => true);
    expect(pendientes.length).toBe(9);
    const con = pendientes.filter((r) => r.request.url.includes('incluir_sinteticos=true'));
    expect(con.length).toBe(7);
    expect(con.map(ruta).sort()).toEqual(
      RUTAS_RONDA.filter((r) => r !== '/comparacion-historica' && r !== '/status').sort(),
    );
    const comparacion = pendientes.find((r) => ruta(r) === '/comparacion-historica')!;
    expect(comparacion.request.url).toBe(`${BASE}/comparacion-historica`);
    expect(pendientes.find((r) => ruta(r) === '/status')!.request.url).toBe(`${BASE}/status`);
    pendientes.forEach((r) => r.flush({}));
    await ronda;
  });

  it('las opciones de país y subregión siguen la vista (REPRODUCCIÓN y sintéticos)', async () => {
    const { http, datos, store } = await preparar();
    store.fijarModo('replay');
    store.fijarSinteticos(true);
    const p = datos.cargarOpciones();
    const pendientes = http.match(() => true);
    expect(pendientes.map((r) => r.request.url).sort()).toEqual([
      `${BASE}/recuentos/pais?modo=replay&incluir_sinteticos=true`,
      `${BASE}/recuentos/subregion?modo=replay&incluir_sinteticos=true`,
    ]);
    pendientes.forEach((r) => r.flush({ total: 0, categorias: [] }));
    await p;
  });
});

describe('FiltrosStore (vista de datos)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('arranca en directo y sin sintéticos', async () => {
    const { store } = await preparar();
    expect(store.vista()).toEqual({ modo: 'live', sinteticos: false });
  });

  it('recargar (store nuevo) vuelve a «en directo» y sin sintéticos: no se persiste', async () => {
    const { store } = await preparar();
    store.fijarModo('replay');
    store.fijarSinteticos(true);
    expect(store.vista()).toEqual({ modo: 'replay', sinteticos: true });
    TestBed.resetTestingModule();
    const { store: nuevo } = await preparar();
    expect(nuevo.vista()).toEqual({ modo: 'live', sinteticos: false });
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('cambiar de modo o de sintéticos vuelve a la página 0 y suelta la selección', async () => {
    const { store } = await preparar();
    store.irAPagina(100);
    store.eventoSeleccionado.set('us1');
    store.fijarModo('replay');
    expect(store.pagina().desplazamiento).toBe(0);
    expect(store.eventoSeleccionado()).toBeNull();

    store.irAPagina(50);
    store.eventoSeleccionado.set('us2');
    store.fijarSinteticos(true);
    expect(store.pagina().desplazamiento).toBe(0);
    expect(store.eventoSeleccionado()).toBeNull();
  });

  it('fijar el mismo valor no cambia la vista (misma referencia) ni toca la página', async () => {
    const { store } = await preparar();
    const antes = store.vista();
    store.irAPagina(50);
    store.fijarModo('live');
    store.fijarSinteticos(false);
    expect(store.vista()).toBe(antes);
    expect(store.pagina().desplazamiento).toBe(50);
  });

  it('se aplica al instante: sin esperar los 400 ms de los filtros de texto', async () => {
    vi.useFakeTimers();
    try {
      const { store } = await preparar();
      store.fijarModo('replay');
      expect(store.vista().modo).toBe('replay');
    } finally {
      vi.useRealTimers();
    }
  });

  it('la vista no altera los filtros editados ni aplicados', async () => {
    const { store } = await preparar();
    store.editar({ magnitudMin: '4' });
    store.aplicarYa();
    store.fijarModo('replay');
    expect(store.aplicados()).toEqual({ magnitudMin: 4 });
    expect(store.editados().magnitudMin).toBe('4');
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

  /** Cuenta las peticiones de la ronda (sin las 2 de opciones: van a /recuentos/pais y /subregion). */
  const conteo = (pendientes: TestRequest[]) => {
    const por: Record<string, number> = {};
    for (const r of pendientes) por[ruta(r)] = (por[ruta(r)] ?? 0) + 1;
    return por;
  };

  it('cambiar a REPRODUCCIÓN dispara una ronda de 8 GET sin comparación (+2 de opciones)', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.fijarModo('replay');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    const pendientes = rutasPendientes(http);
    expect(pendientes.length).toBe(10);
    const por = conteo(pendientes);
    expect(por['/comparacion-historica']).toBeUndefined();
    expect(por['/status']).toBe(1);
    expect(por['/eventos']).toBe(1);
    expect(por['/eventos/mapa']).toBe(1);
    // /recuentos/pais y /subregion: uno de la ronda y uno de las opciones.
    expect(por['/recuentos/pais']).toBe(2);
    expect(por['/recuentos/subregion']).toBe(2);
    expect(
      pendientes.filter((r) => ruta(r) !== '/status').every((r) => r.request.url.includes('modo=replay')),
    ).toBe(true);
    pendientes.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('en REPRODUCCIÓN el refresco de 60 s sigue sin pedir la comparación', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    store.fijarModo('replay');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    await vi.advanceTimersByTimeAsync(60_000);
    const ronda = rutasPendientes(http);
    expect(ronda.length).toBe(8);
    expect(ronda.map(ruta)).not.toContain('/comparacion-historica');
    ronda.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('volver a «En directo» recupera la comparación y quita `modo` de las peticiones', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    store.fijarModo('replay');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.fijarModo('live');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    const pendientes = rutasPendientes(http);
    expect(pendientes.length).toBe(11);
    expect(conteo(pendientes)['/comparacion-historica']).toBe(1);
    expect(pendientes.some((r) => r.request.url.includes('modo'))).toBe(false);
    pendientes.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('el interruptor de sintéticos dispara una ronda de 9 GET; la comparación no lo lleva', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.fijarSinteticos(true);
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    const pendientes = rutasPendientes(http);
    expect(pendientes.length).toBe(11);
    const comparacion = pendientes.filter((r) => ruta(r) === '/comparacion-historica');
    expect(comparacion.length).toBe(1);
    expect(comparacion[0].request.url).toBe(`${BASE}/comparacion-historica`);
    expect(
      pendientes
        .filter((r) => !['/status', '/comparacion-historica'].includes(ruta(r)))
        .every((r) => r.request.url.includes('incluir_sinteticos=true')),
    ).toBe(true);
    pendientes.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('cambiar de modo estando en la página 3 pide la tabla desde el principio, una sola vez', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    store.irAPagina(100);
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.fijarModo('replay');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    const pendientes = rutasPendientes(http);
    const tablas = pendientes.filter((r) => ruta(r) === '/eventos');
    expect(tablas.length).toBe(1);
    expect(tablas[0].request.url).toContain('desplazamiento=0');
    pendientes.forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);
  });

  it('fijar el mismo modo no dispara ninguna petición', async () => {
    const { http, store } = await arrancar();
    rutasPendientes(http).forEach((r) => r.flush({}));
    await vi.advanceTimersByTimeAsync(0);

    store.fijarModo('live');
    store.fijarSinteticos(false);
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    expect(rutasPendientes(http).length).toBe(0);
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
