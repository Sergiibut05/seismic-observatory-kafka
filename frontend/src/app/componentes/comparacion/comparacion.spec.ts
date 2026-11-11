import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ComparacionHistorica } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
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
  ventana_actual: {
    desde: '2026-11-01T16:00:00.000Z',
    hasta: '2026-11-02T16:00:00.000Z',
    eventos: 30,
  },
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

  it('dos barras sobre la misma escala y el cociente dicho en palabras', async () => {
    const el = await montar(bloque(COMP));
    const largo = (sel: string) => (el.querySelector(sel) as HTMLElement).style.inlineSize;
    // 30 frente a 50: la media llena la pista y las últimas 24 h llegan al 60 %.
    expect(largo('.cifra--media .cifra__barra span')).toBe('100%');
    expect(largo('.cifra--actual .cifra__barra span')).toBe('60%');
    const veredicto = el.querySelector('.cifra__veredicto')!;
    expect(veredicto.textContent?.trim()).toBe('40 % por debajo de la media diaria');
    expect(veredicto.getAttribute('data-sentido')).toBe('debajo');
    // Las barras son un apoyo visual: las cifras ya están en el texto.
    for (const b of el.querySelectorAll('.cifra__barra'))
      expect(b.getAttribute('aria-hidden')).toBe('true');
  });

  it('el aviso de periodo incompleto está siempre visible', async () => {
    const el = await montar(bloque(COMP));
    expect(el.querySelector('.comparacion__aviso')?.textContent).toContain(
      'puede estar incompleto',
    );
    TestBed.resetTestingModule();
    // También sin datos (cargando): aviso de respaldo
    const cargando = await montar(
      bloque<ComparacionHistorica>(null, { estado: 'cargando', lecturaOk: null }),
    );
    expect(cargando.querySelector('.comparacion__aviso')?.textContent).toContain(
      'puede estar incompleto',
    );
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
    // Sin media no hay barra de 2025 ni veredicto: nada que parezca un dato.
    expect(el.querySelectorAll('.cifra__barra')).toHaveLength(1);
    expect(el.querySelector('.cifra__veredicto')).toBeNull();
    expect(el.querySelector('.comparacion__aviso')).not.toBeNull();
  });

  describe('REPRODUCCIÓN (007)', () => {
    async function montarReplay(b: Bloque<ComparacionHistorica>) {
      TestBed.configureTestingModule({
        providers: [{ provide: PanelDatosService, useValue: { comparacion: signal(b) } }],
      });
      TestBed.inject(FiltrosStore).fijarModo('replay');
      const fixture = TestBed.createComponent(Comparacion);
      await fixture.whenStable();
      return { fixture, el: fixture.nativeElement as HTMLElement };
    }

    it('dice que la comparación histórica solo existe en directo', async () => {
      const { el } = await montarReplay(
        bloque<ComparacionHistorica>(null, { estado: 'cargando', lecturaOk: null }),
      );
      expect(el.querySelector('.comparacion__solo-directo')?.textContent).toContain(
        'La comparación histórica solo existe en directo',
      );
      expect(el.querySelector('.bloque__nota')?.textContent).toContain('Solo existe en directo');
    });

    it('no inventa cifras: ni 24 h, ni media, ni cociente, ni ceros', async () => {
      const { el } = await montarReplay(
        bloque<ComparacionHistorica>(null, { estado: 'cargando', lecturaOk: null }),
      );
      expect(el.querySelector('dl')).toBeNull();
      expect(el.querySelector('.cifra__valor')).toBeNull();
      expect(el.querySelector('.comparacion__filtros')).toBeNull();
      expect(el.textContent).not.toMatch(
        /Últimas 24 h|Media diaria de 2025|Cociente|Filtro efectivo/,
      );
    });

    it('tampoco muestra la última lectura en directo que hubiera quedado en el bloque', async () => {
      const { el } = await montarReplay(bloque(COMP));
      expect(el.textContent).not.toContain('0,6');
      expect(el.textContent).not.toContain('Media diaria de 2025');
      expect(el.querySelector('.comparacion__aviso')).toBeNull();
    });

    it('al volver a «En directo» reaparecen las cifras', async () => {
      const { fixture, el } = await montarReplay(bloque(COMP));
      TestBed.inject(FiltrosStore).fijarModo('live');
      await fixture.whenStable();
      expect(el.querySelector('.comparacion__solo-directo')).toBeNull();
      expect(el.textContent).toContain('Media diaria de 2025');
    });
  });

  it('error con datos antiguos: etiquetados', async () => {
    const el = await montar(
      bloque(COMP, {
        estado: 'error',
        error: { tipo: 'red', motivo: 'Sin conexión con la API', status: 0, parametro: null },
      }),
    );
    expect(el.textContent).toContain('Datos desactualizados');
    expect(el.textContent).toContain('0,6');
    expect(el.querySelector('[role="alert"]')).toBeNull();
  });
});
