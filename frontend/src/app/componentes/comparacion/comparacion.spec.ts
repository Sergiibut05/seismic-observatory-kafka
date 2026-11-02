import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ComparacionHistorica } from '../../modelos/api';
import { Bloque, PanelDatosService } from '../../nucleo/panel-datos.service';
import { Comparacion } from './comparacion';

const bloque = <T>(datos: T | null, extra: Partial<Bloque<T>> = {}): Bloque<T> => ({
  estado: 'ok',
  datos,
  lecturaOk: Date.parse('2026-11-02T16:00:00Z'),
  error: null,
  ...extra,
});

const COMP: ComparacionHistorica = {
  ventana_actual: { desde: '2026-11-01T16:00:00.000Z', hasta: '2026-11-02T16:00:00.000Z', eventos: 30 },
  historico_2025: { estado: 'cargado', eventos: 18250, dias: 365, media_diaria: 50 },
  cociente: 0.6,
  filtros_efectivos: { magnitud_min: 4, magnitud_max: null, pais: null, subregion: null },
  aviso: 'El último periodo puede estar incompleto: USGS publica con retraso.',
  generated_at: '2026-11-02T16:00:00.000Z',
};

async function montar(b: Bloque<ComparacionHistorica>) {
  TestBed.configureTestingModule({
    providers: [{ provide: PanelDatosService, useValue: { comparacion: signal(b) } }],
  });
  const fixture = TestBed.createComponent(Comparacion);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Comparacion', () => {
  it('muestra 24 h, media 2025, cociente 0,6 y el filtro efectivo', async () => {
    const el = await montar(bloque(COMP));
    const texto = el.textContent ?? '';
    expect(el.querySelector('dl .cifra__valor')?.textContent?.trim()).toBe('30');
    expect(texto).toContain('Media diaria de 2025');
    expect(texto).toContain('0,6');
    expect(texto).toContain('Filtro efectivo: magnitud ≥ 4,0 · país: todos · subregión: todas');
    expect(texto).toContain('Solo usa magnitud y país/subregión');
  });

  it('el aviso de periodo incompleto está siempre visible', async () => {
    const el = await montar(bloque(COMP));
    expect(el.querySelector('.comparacion__aviso')?.textContent).toContain('puede estar incompleto');
    TestBed.resetTestingModule();
    // También sin datos (cargando): aviso de respaldo
    const cargando = await montar(bloque<ComparacionHistorica>(null, { estado: 'cargando', lecturaOk: null }));
    expect(cargando.querySelector('.comparacion__aviso')?.textContent).toContain('puede estar incompleto');
  });

  it('no_cargado: «no disponible» y nunca 0', async () => {
    const el = await montar(
      bloque({
        ...COMP,
        historico_2025: { estado: 'no_cargado', eventos: null, dias: 0, media_diaria: null },
        cociente: null,
      }),
    );
    const valores = [...el.querySelectorAll('.cifra__valor')].map((e) => e.textContent?.trim());
    expect(valores).toEqual(['30', 'no disponible', 'no disponible']);
    expect(el.textContent).toContain('no está cargado');
    expect(el.querySelector('.comparacion__aviso')).not.toBeNull();
  });

  it('error con datos antiguos: etiquetados', async () => {
    const el = await montar(
      bloque(COMP, { estado: 'error', error: { tipo: 'red', motivo: 'Sin conexión con la API', status: 0, parametro: null } }),
    );
    expect(el.textContent).toContain('Datos desactualizados');
    expect(el.textContent).toContain('0,6');
    expect(el.querySelector('[role="alert"]')).toBeNull();
  });
});
