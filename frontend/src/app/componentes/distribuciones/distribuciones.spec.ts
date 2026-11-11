import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Distribucion } from '../../modelos/api';
import { Bloque, PanelDatosService } from '../../nucleo/panel-datos.service';
import { Distribuciones } from './distribuciones';

const bloque = <T>(datos: T | null, extra: Partial<Bloque<T>> = {}): Bloque<T> => ({
  estado: 'ok',
  datos,
  lecturaOk: Date.parse('2026-11-02T16:00:00Z'),
  error: null,
  ...extra,
});

const MAGNITUD: Distribucion = {
  unidad: 'magnitud',
  total: 12,
  sin_valor: 2,
  intervalos: [
    { desde: null, hasta: 0, etiqueta: '< 0', recuento: 0 },
    { desde: 0, hasta: 1, etiqueta: '0–1', recuento: 4 },
    { desde: 1, hasta: 2, etiqueta: '1–2', recuento: 6 },
    { desde: 2, hasta: null, etiqueta: '≥ 2', recuento: 0 },
  ],
};
const PROFUNDIDAD: Distribucion = {
  unidad: 'km',
  total: 5,
  sin_valor: 0,
  intervalos: [
    { desde: null, hasta: 0, etiqueta: '< 0', recuento: 1 },
    { desde: 0, hasta: 10, etiqueta: '0–10', recuento: 4 },
  ],
};

async function montar(
  mag: Bloque<Distribucion> = bloque(MAGNITUD),
  prof: Bloque<Distribucion> = bloque(PROFUNDIDAD),
) {
  TestBed.configureTestingModule({
    providers: [
      {
        provide: PanelDatosService,
        useValue: { distMagnitud: signal(mag), distProfundidad: signal(prof) },
      },
    ],
  });
  const fixture = TestBed.createComponent(Distribuciones);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Distribuciones', () => {
  it('sin_valor: 2 se ve aparte, no mezclado con el intervalo 0–1 ni con ceros', async () => {
    const el = await montar();
    const parte = el.querySelector('section[aria-labelledby="titulo-dist-magnitud"]')!;
    // 4 intervalos + la categoría «Sin valor»
    expect(parte.querySelectorAll('g.grafico__barra')).toHaveLength(5);
    const sin = parte.querySelector('g[data-tipo="sin-valor"]')!;
    expect(sin.querySelector('text.grafico__valor')?.textContent?.trim()).toBe('2');
    const primero = parte.querySelectorAll('g.grafico__barra')[1];
    expect(primero.querySelector('text.grafico__valor')?.textContent?.trim()).toBe('4');
    expect(parte.textContent).toContain('2 sin magnitud registrada (no cuentan como 0)');
    // Los intervalos a cero se ven como cero, no como «sin valor»
    expect(parte.querySelectorAll('g[data-tipo="cero"]')).toHaveLength(2);
  });

  it('con sin_valor 0 la categoría aparte sigue ahí y es distinta de ND', async () => {
    const el = await montar();
    const parte = el.querySelector('section[aria-labelledby="titulo-dist-profundidad"]')!;
    const sin = parte.querySelector('g[data-tipo="sin-valor"]')!;
    expect(sin.querySelector('text.grafico__valor')?.textContent?.trim()).toBe('0');
    expect(parte.querySelector('g[data-tipo="nd"]')).toBeNull();
  });

  it('usa la etiqueta de la API y la unidad en la tabla equivalente', async () => {
    const el = await montar();
    const parte = el.querySelector('section[aria-labelledby="titulo-dist-profundidad"]')!;
    expect(parte.querySelector('details tbody th')?.textContent).toContain('< 0');
    expect(parte.textContent).toContain('0–10 km');
  });

  it('datos clave: total e intervalo más frecuente con su parte del total', async () => {
    const el = await montar();
    const mag = el.querySelector('section[aria-labelledby="titulo-dist-magnitud"] .datos-clave')!;
    expect(mag.textContent).toContain('12');
    expect(mag.textContent).toContain('1–2');
    expect(mag.textContent).toContain('50,0 %');
    const prof = el.querySelector(
      'section[aria-labelledby="titulo-dist-profundidad"] .datos-clave',
    )!;
    expect(prof.textContent).toContain('0–10 km');
    expect(prof.textContent).toContain('80,0 %');
  });

  it('la profundidad lleva bajo el eje los colores del mapa; la magnitud, no', async () => {
    const el = await montar();
    const claves = (id: string) =>
      [...el.querySelectorAll(`section[aria-labelledby="${id}"] path.grafico__clave`)].map((p) =>
        p.getAttribute('fill'),
      );
    expect(claves('titulo-dist-profundidad')).toEqual(['#c2185b', '#ffffb2']);
    expect(claves('titulo-dist-magnitud')).toEqual([]);
  });

  it('estado vacío y datos antiguos', async () => {
    const vacio = await montar(
      bloque<Distribucion>({ ...MAGNITUD, total: 0, sin_valor: 0, intervalos: [] }),
    );
    expect(vacio.textContent).toContain('No hay eventos que cumplan los filtros actuales.');
    TestBed.resetTestingModule();
    const antiguos = await montar(
      bloque(MAGNITUD, {
        estado: 'error',
        error: { tipo: 'red', motivo: 'Sin conexión con la API', status: 0, parametro: null },
      }),
    );
    expect(antiguos.textContent).toContain('Datos desactualizados');
    expect(antiguos.querySelectorAll('g[data-tipo="sin-valor"]').length).toBeGreaterThan(0);
  });
});
