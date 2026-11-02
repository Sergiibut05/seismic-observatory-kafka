import { TestBed } from '@angular/core/testing';
import { DatoBarra } from '../../puro/barras';
import { GraficoBarras, Orientacion } from './grafico-barras';

async function montar(datos: DatoBarra[], orientacion: Orientacion = 'horizontal', filasTabla?: DatoBarra[]) {
  const fixture = TestBed.createComponent(GraficoBarras);
  fixture.componentRef.setInput('titulo', 'Eventos por país');
  fixture.componentRef.setInput('datos', datos);
  fixture.componentRef.setInput('orientacion', orientacion);
  if (filasTabla) fixture.componentRef.setInput('filasTabla', filasTabla);
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
        expect(Number(cero?.getAttribute('width')) * Number(cero?.getAttribute('height'))).toBeGreaterThan(0);
        expect(el.querySelector('g[data-tipo="cero"] text.grafico__valor')?.textContent?.trim()).toBe('0');
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
    const el = await montar(
      [d('A', 5), d('Resto (2)', 3)],
      'horizontal',
      [d('A', 5), d('B', 2), d('C', 1)],
    );
    expect(el.querySelectorAll('g.grafico__barra')).toHaveLength(2);
    expect(el.querySelectorAll('details table tbody tr')).toHaveLength(3);
  });

  it('con 48 ventanas no se pintan las 48 etiquetas, pero sí las 48 barras', async () => {
    const datos = Array.from({ length: 48 }, (_, i) => d(`v${i}`, i % 4 === 0 ? 0 : i));
    const el = await montar(datos, 'vertical');
    expect(el.querySelectorAll('g.grafico__barra')).toHaveLength(48);
    expect(el.querySelectorAll('text.grafico__etiqueta').length).toBeLessThan(48);
    expect(el.querySelectorAll('g[data-tipo="cero"]')).toHaveLength(12);
  });
});
