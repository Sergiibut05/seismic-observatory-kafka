import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { EstadoApi } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { Bloque, PanelDatosService } from '../../nucleo/panel-datos.service';
import { calcularEstado } from '../../puro/desactualizado';
import { Estado } from './estado';

const estadoApi = (parcial: Partial<EstadoApi>): EstadoApi => ({
  base_de_datos: 'conectada',
  eventos_reales: 12,
  eventos_sinteticos: 0,
  eventos_replay: 0,
  ultimo_evento: null,
  ultima_ingesta_correcta: '2026-11-02T16:00:00.000Z',
  periodo_consultado: { desde: '2026-11-01T16:00:00.000Z', hasta: '2026-11-02T16:00:00.000Z' },
  datos_desactualizados: false,
  umbral_datos_desactualizados_segundos: 300,
  generated_at: '2026-11-02T16:00:00.000Z',
  ...parcial,
});

const bloque = (datos: EstadoApi | null): Bloque<EstadoApi> => ({
  estado: datos ? 'ok' : 'error',
  datos,
  lecturaOk: datos ? Date.parse('2026-11-02T16:00:00Z') : null,
  error: datos ? null : { tipo: 'red', motivo: 'caída', status: 0, parametro: null },
});

async function montar(b: Bloque<EstadoApi>) {
  TestBed.configureTestingModule({
    providers: [
      {
        provide: PanelDatosService,
        useValue: {
          status: signal(b),
          ultimoAccesoOk: signal(b.lecturaOk),
          estadoSistema: signal(calcularEstado(b.datos, b.datos === null)),
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(Estado);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Estado', () => {
  it('muestra ND si no hay eventos reales', async () => {
    const el = await montar(bloque(estadoApi({ eventos_reales: null })));
    expect(el.textContent).toContain('ND');
  });

  it('avisa si los datos están desactualizados', async () => {
    const el = await montar(bloque(estadoApi({ datos_desactualizados: true })));
    expect(el.textContent).toContain('desactualizados');
  });

  describe('REPRODUCCIÓN (007)', () => {
    async function montarEn(modo: 'live' | 'replay', parcial: Partial<EstadoApi> = {}) {
      const b = bloque(estadoApi(parcial));
      TestBed.configureTestingModule({
        providers: [
          {
            provide: PanelDatosService,
            useValue: {
              status: signal(b),
              ultimoAccesoOk: signal(b.lecturaOk),
              estadoSistema: signal(calcularEstado(b.datos, false)),
            },
          },
        ],
      });
      TestBed.inject(FiltrosStore).fijarModo(modo);
      const fixture = TestBed.createComponent(Estado);
      await fixture.whenStable();
      return fixture.nativeElement as HTMLElement;
    }

    it('en directo no muestra «Eventos en reproducción»', async () => {
      const el = await montarEn('live', { eventos_replay: 25 });
      expect(el.textContent).not.toContain('Eventos en reproducción');
    });

    it('en REPRODUCCIÓN muestra los eventos de la reproducción, aparte de los reales', async () => {
      const el = await montarEn('replay', { eventos_replay: 25, eventos_reales: 12 });
      const valores = Object.fromEntries(
        Array.from(el.querySelectorAll('dl dt')).map((dt) => [dt.textContent?.trim(), dt.nextElementSibling?.textContent?.trim()]),
      );
      expect(valores['Eventos en reproducción']).toBe('25');
      expect(valores['Eventos reales']).toBe('12');
    });

    it('con `eventos_replay` nulo (sin base de datos) muestra «ND», no 0', async () => {
      const el = await montarEn('replay', { eventos_replay: null });
      const fila = el.querySelector('.estado__replay dd');
      expect(fila?.textContent?.trim()).toBe('ND');
    });

    it('con 0 eventos reproducidos muestra 0 (un cero real, no un dato desconocido)', async () => {
      const el = await montarEn('replay', { eventos_replay: 0 });
      expect(el.querySelector('.estado__replay dd')?.textContent?.trim()).toBe('0');
    });
  });

  it('con la API caída usa un único aviso de alerta', async () => {
    const el = await montar(bloque(null));
    expect(el.querySelectorAll('[role="alert"]').length).toBe(1);
    expect(el.textContent).toContain('La API no responde');
  });
});
