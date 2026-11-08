import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { RespuestaMapa } from '../../modelos/api';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { Mapa } from './mapa';

const respuesta = (truncado: boolean): RespuestaMapa => ({
  type: 'FeatureCollection',
  modo: 'live',
  features: [],
  total: 7312,
  devueltos: 5000,
  limite: 5000,
  truncado,
  generated_at: '2026-11-02T10:00:00.000Z',
});

// En jsdom Leaflet no se inicia (MAPA_HABILITADO = false): aquí solo avisos, estado y leyenda.
function montar(r: RespuestaMapa | null) {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  const datos = TestBed.inject(PanelDatosService);
  if (r) datos.mapa.set({ estado: 'ok', datos: r, lecturaOk: Date.now(), error: null });
  const fixture = TestBed.createComponent(Mapa);
  fixture.detectChanges();
  return { fixture, datos, el: fixture.nativeElement as HTMLElement };
}

describe('Mapa (avisos y estado; el dibujo se comprueba en navegador real)', () => {
  it('truncado=true muestra «5000 de 7312»', () => {
    const { el } = montar(respuesta(true));
    expect(el.textContent).toContain('5000 de 7312');
  });

  it('truncado=false no muestra el aviso', () => {
    const { el } = montar(respuesta(false));
    expect(el.textContent).not.toContain('límite de la API');
  });

  it('un error con datos previos muestra el motivo y la etiqueta de desactualizados', () => {
    const { fixture, datos, el } = montar(respuesta(false));
    datos.mapa.update((b) => ({
      ...b,
      estado: 'error',
      error: { tipo: 'red', motivo: 'sin conexión con la API', status: 0, parametro: null },
    }));
    fixture.detectChanges();
    expect(el.textContent).toContain('sin conexión con la API');
    expect(el.textContent).toContain('desactualizados');
  });

  describe('REPRODUCCIÓN y sintéticos (007)', () => {
    it('en directo y sin sintéticos: ni nota de reproducción ni entrada «SINTÉTICO» en la leyenda', () => {
      const { el } = montar(respuesta(false));
      expect(el.textContent).not.toContain('REPRODUCCIÓN');
      expect(el.textContent).not.toContain('SINTÉTICO');
    });

    it('con datos de replay lo rotula en la cabecera del mapa', () => {
      const { el } = montar({ ...respuesta(false), modo: 'replay' });
      expect(el.querySelector('.bloque__nota')?.textContent).toContain('REPRODUCCIÓN');
    });

    it('la cabecera vuelve a su texto al recibir datos en directo', () => {
      const { fixture, datos, el } = montar({ ...respuesta(false), modo: 'replay' });
      datos.mapa.update((b) => ({ ...b, datos: respuesta(false) }));
      fixture.detectChanges();
      expect(el.querySelector('.bloque__nota')?.textContent).not.toContain('REPRODUCCIÓN');
    });
  });

  it('un error sin datos no habla de datos antiguos', () => {
    const { fixture, datos, el } = montar(null);
    datos.mapa.update((b) => ({
      ...b,
      estado: 'error',
      error: { tipo: 'red', motivo: 'sin conexión con la API', status: 0, parametro: null },
    }));
    fixture.detectChanges();
    expect(el.textContent).toContain('No se pudo cargar el mapa');
    expect(el.textContent).not.toContain('desactualizados');
  });
});
