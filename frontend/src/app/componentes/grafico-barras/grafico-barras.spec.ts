import { TestBed } from '@angular/core/testing';
import { DatoBarra } from '../../puro/barras';
import { GraficoBarras, Orientacion } from './grafico-barras';

async function montar(
  datos: DatoBarra[],
  orientacion: Orientacion = 'horizontal',
  filasTabla?: DatoBarra[],
  extra: Record<string, unknown> = {},
) {
  const fixture = TestBed.createComponent(GraficoBarras);
  fixture.componentRef.setInput('titulo', 'Eventos por país');
  fixture.componentRef.setInput('datos', datos);
  fixture.componentRef.setInput('orientacion', orientacion);
  if (filasTabla) fixture.componentRef.setInput('filasTabla', filasTabla);
  for (const [k, v] of Object.entries(extra)) fixture.componentRef.setInput(k, v);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

const d = (clave: string, valor: number | null, extra: Partial<DatoBarra> = {}): DatoBarra => ({
  clave,
  etiqueta: clave,
  valor,
  ...extra,
});

describe('GraficoBarras', () => {
  for (const orientacion of ['horizontal', 'vertical'] as const) {
    describe(orientacion, () => {
      it('una barra por categoría; la de cero sigue presente', async () => {
        const el = await montar([d('Chile', 5), d('Perú', 0), d('Japón', 2)], orientacion);
        expect(el.querySelectorAll('g.grafico__barra')).toHaveLength(3);
        const cero = el.querySelector('g[data-tipo="cero"] rect');
        expect(cero).not.toBeNull();
        expect(
          Number(cero?.getAttribute('width')) * Number(cero?.getAttribute('height')),
        ).toBeGreaterThan(0);
        expect(
          el.querySelector('g[data-tipo="cero"] text.grafico__valor')?.textContent?.trim(),
        ).toBe('0');
      });

      it('role="img" con aria-label descriptivo y tabla equivalente con todas las filas', async () => {
        const el = await montar([d('Chile', 5), d('Perú', 0)], orientacion);
        const svg = el.querySelector('svg')!;
        expect(svg.getAttribute('role')).toBe('img');
        const etiqueta = svg.getAttribute('aria-label') ?? '';
        expect(etiqueta).toContain('Eventos por país');
        expect(etiqueta).toContain('Mayor: Chile, 5');
        const filas = el.querySelectorAll('details table tbody tr');
        expect(filas).toHaveLength(2);
        expect(filas[1].textContent).toContain('Sin eventos (0)');
      });

      it('«sin valor» y «ND» son distintos del cero', async () => {
        const el = await montar(
          [d('1–2', 3), d('2–3', 0), d('Desconocida', null), d('Sin valor', 2, { sinValor: true })],
          orientacion,
        );
        expect(el.querySelectorAll('g[data-tipo="cero"]')).toHaveLength(1);
        expect(el.querySelectorAll('g[data-tipo="sin-valor"] rect')).toHaveLength(1);
        const nd = el.querySelector('g[data-tipo="nd"]')!;
        expect(nd.querySelector('rect')).toBeNull();
        expect(nd.textContent).toContain('ND');
        const sin = el.querySelector('g[data-tipo="sin-valor"] text.grafico__valor');
        expect(sin?.textContent?.trim()).toBe('2');
        const leyenda = el.querySelector('.grafico__leyenda')?.textContent ?? '';
        expect(leyenda).toContain('no son 0');
        const tabla = el.querySelector('details table')?.textContent ?? '';
        expect(tabla).toContain('Eventos sin valor registrado');
        expect(tabla).toContain('Valor desconocido (ND)');
      });
    });
  }

  it('la tabla puede tener más filas que el gráfico (resto agrupado)', async () => {
    const el = await montar([d('A', 5), d('Resto (2)', 3)], 'horizontal', [
      d('A', 5),
      d('B', 2),
      d('C', 1),
    ]);
    expect(el.querySelectorAll('g.grafico__barra')).toHaveLength(2);
    expect(el.querySelectorAll('details table tbody tr')).toHaveLength(3);
  });

  it('con cuota, la lista da la parte del total de cada barra y la ficha también', async () => {
    const el = await montar([d('Chile', 3), d('Perú', 1)], 'horizontal', undefined, {
      cuota: true,
    });
    const cuotas = [...el.querySelectorAll('text.grafico__cuota')].map((t) =>
      t.textContent?.trim(),
    );
    expect(cuotas).toEqual(['75,0 %', '25,0 %']);
    expect(el.querySelector('.grafico__tip')).toBeNull();
    el.querySelector('g.grafico__barra')!.dispatchEvent(new Event('mouseenter'));
    await new Promise((r) => setTimeout(r));
    const ficha = el.querySelector('.grafico__tip')!;
    expect(ficha.textContent).toContain('Chile');
    expect(ficha.textContent).toContain('75,0 %');
    expect(ficha.getAttribute('aria-hidden')).toBe('true');
  });

  it('sin cuota no hay columna de porcentajes', async () => {
    const el = await montar([d('Chile', 3), d('Perú', 1)]);
    expect(el.querySelector('text.grafico__cuota')).toBeNull();
  });

  it('la referencia se dibuja solo si cabe en la escala y solo en vertical', async () => {
    const datos = [d('a', 4), d('b', 8)];
    const con = await montar(datos, 'vertical', undefined, {
      referencia: { valor: 6, etiqueta: 'media 6' },
    });
    expect(con.querySelector('.grafico__referencia text')?.textContent?.trim()).toBe('media 6');
    TestBed.resetTestingModule();
    const fuera = await montar(datos, 'vertical', undefined, {
      referencia: { valor: 60, etiqueta: 'media 60' },
    });
    expect(fuera.querySelector('.grafico__referencia')).toBeNull();
    TestBed.resetTestingModule();
    const lista = await montar(datos, 'horizontal', undefined, {
      referencia: { valor: 6, etiqueta: 'media 6' },
    });
    expect(lista.querySelector('.grafico__referencia')).toBeNull();
  });

  it('la clave de color bajo el eje solo aparece en las barras que la traen', async () => {
    const el = await montar(
      [
        d('0–10', 4, { color: '#ffffb2' }),
        d('10–30', 2, { color: '#d9f0a3' }),
        d('Sin valor', 0, { sinValor: true }),
      ],
      'vertical',
    );
    const claves = [...el.querySelectorAll('path.grafico__clave')].map((p) =>
      p.getAttribute('fill'),
    );
    expect(claves).toEqual(['#ffffb2', '#d9f0a3']);
  });

  it('la rejilla es de filete continuo: nada discontinuo salvo la referencia y «sin valor»', async () => {
    const el = await montar([d('a', 4), d('b', 8)], 'vertical');
    expect(el.querySelectorAll('line.grafico__guia').length).toBeGreaterThan(0);
    expect(el.querySelector('line.grafico__guia[stroke-dasharray]')).toBeNull();
  });

  it('con 48 ventanas no se pintan las 48 etiquetas, pero sí las 48 barras', async () => {
    const datos = Array.from({ length: 48 }, (_, i) => d(`v${i}`, i % 4 === 0 ? 0 : i));
    const el = await montar(datos, 'vertical');
    expect(el.querySelectorAll('g.grafico__barra')).toHaveLength(48);
    expect(el.querySelectorAll('text.grafico__etiqueta').length).toBeLessThan(48);
    expect(el.querySelectorAll('g[data-tipo="cero"]')).toHaveLength(12);
  });
});
