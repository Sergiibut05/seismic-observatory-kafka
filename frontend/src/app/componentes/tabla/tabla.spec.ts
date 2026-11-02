import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EventoTabla, RespuestaEventos } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { Tabla } from './tabla';

const evento = (n: number, extra: Partial<EventoTabla> = {}): EventoTabla => ({
  event_id: `us${n}`,
  ocurrencia: '2026-11-02T10:00:00.000Z',
  updated: '2026-11-02T11:00:00.000Z',
  magnitud: 4.2,
  profundidad: 12,
  longitud: -100,
  latitud: 20,
  pais_codigo: 'MEX',
  pais_nombre: 'México',
  subregion: 'América Central',
  sintetico: false,
  ...extra,
});

function respuesta(eventos: EventoTabla[], total: number, desplazamiento = 0): RespuestaEventos {
  return { eventos, total, limite: 50, desplazamiento };
}

function montar(r: RespuestaEventos) {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  const datos = TestBed.inject(PanelDatosService);
  datos.tabla.set({ estado: 'ok', datos: r, lecturaOk: Date.now(), error: null });
  const fixture = TestBed.createComponent(Tabla);
  fixture.detectChanges();
  return { fixture, datos, store: TestBed.inject(FiltrosStore), el: fixture.nativeElement as HTMLElement };
}

describe('Tabla', () => {
  it('es una tabla accesible con caption y cabeceras con scope, y muestra el total filtrado', () => {
    const { el } = montar(respuesta([evento(1)], 312));
    expect(el.querySelector('table caption')?.textContent).toContain('312 eventos');
    const cabeceras = el.querySelectorAll('thead th');
    expect(cabeceras.length).toBeGreaterThan(5);
    cabeceras.forEach((th) => expect(th.getAttribute('scope')).toBe('col'));
    expect(el.querySelector('tbody th')?.getAttribute('scope')).toBe('row');
  });

  it('una magnitud nula se muestra «ND», no 0', () => {
    const { el } = montar(respuesta([evento(1, { magnitud: null, profundidad: null })], 1));
    const celdas = Array.from(el.querySelectorAll('tbody td.num')).map((c) => c.textContent?.trim());
    expect(celdas).toEqual(['ND', 'ND']);
  });

  it('mantiene el orden que devuelve la API', () => {
    const { el } = montar(respuesta([evento(3), evento(1), evento(2)], 3));
    const ids = Array.from(el.querySelectorAll('tbody .tabla__id')).map((c) => c.textContent?.trim());
    expect(ids).toEqual(['us3', 'us1', 'us2']);
  });

  it('«Siguiente» pide la página 2 con desplazamiento 50; «Anterior» está desactivado en la primera', () => {
    const { fixture, el, store } = montar(respuesta([evento(1)], 312));
    const [anterior, siguiente] = Array.from(el.querySelectorAll<HTMLButtonElement>('nav button'));
    expect(anterior.disabled).toBe(true);
    expect(el.querySelector('nav')?.textContent).toContain('Página 1 de 7');
    siguiente.click();
    fixture.detectChanges();
    expect(store.pagina()).toEqual({ limite: 50, desplazamiento: 50 });
  });

  it('en la última página «Siguiente» está desactivado', () => {
    const { el } = montar(respuesta([evento(1)], 60, 50));
    const [anterior, siguiente] = Array.from(el.querySelectorAll<HTMLButtonElement>('nav button'));
    expect(anterior.disabled).toBe(false);
    expect(siguiente.disabled).toBe(true);
  });

  it('«Ver en el mapa» fija el evento seleccionado y lo marca', () => {
    const { fixture, el, store } = montar(respuesta([evento(1), evento(2)], 2));
    const botones = el.querySelectorAll<HTMLButtonElement>('tbody button');
    botones[1].click();
    fixture.detectChanges();
    expect(store.eventoSeleccionado()).toBe('us2');
    expect(botones[1].getAttribute('aria-pressed')).toBe('true');
    expect(botones[0].getAttribute('aria-pressed')).toBe('false');
    expect(el.querySelectorAll('tr.seleccionada').length).toBe(1);
  });

  it('con un error conserva las filas y etiqueta los datos como desactualizados', () => {
    const { fixture, datos, el } = montar(respuesta([evento(1)], 1));
    datos.tabla.update((b) => ({
      ...b,
      estado: 'error',
      error: { tipo: 'servicio_no_disponible', motivo: 'servicio no disponible', status: 503, parametro: null },
    }));
    fixture.detectChanges();
    expect(el.querySelector('.aviso')?.textContent).toContain('desactualizados');
    expect(el.querySelectorAll('tbody tr').length).toBe(1);
  });

  it('sin eventos lo dice, sin tabla vacía', () => {
    const { el } = montar(respuesta([], 0));
    expect(el.querySelector('table')).toBeNull();
    expect(el.textContent).toContain('Ningún evento');
  });
});
