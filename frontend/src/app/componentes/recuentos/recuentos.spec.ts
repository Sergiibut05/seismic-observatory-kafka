import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { RecuentosHora, RecuentosPais, RecuentosSubregion } from '../../modelos/api';
import { Bloque, PanelDatosService } from '../../nucleo/panel-datos.service';
import { Recuentos } from './recuentos';

function bloque<T>(datos: T | null, extra: Partial<Bloque<T>> = {}): Bloque<T> {
  return { estado: 'ok', datos, lecturaOk: Date.parse('2026-11-02T16:00:00Z'), error: null, ...extra };
}

const PAIS: RecuentosPais = {
  total: 60,
  categorias: [
    { codigo: 'CHL', nombre: 'Chile', recuento: 10 },
    { codigo: null, nombre: 'Sin país asignado', recuento: 50 },
  ],
};
const SUBREGION: RecuentosSubregion = {
  total: 60,
  categorias: [
    { nombre: 'South America', recuento: 10 },
    { nombre: 'Sin país asignado', recuento: 50 },
  ],
};
/** 24 ventanas, 3 en cero. */
const HORA: RecuentosHora = {
  desde: '2026-11-01T16:00:00.000Z',
  hasta: '2026-11-02T16:00:00.000Z',
  total: 100,
  ventanas: Array.from({ length: 24 }, (_, i) => ({
    inicio: new Date(Date.UTC(2026, 10, 1, 16 + i)).toISOString(),
    recuento: i % 8 === 3 ? 0 : i + 1,
  })),
};

async function montar(
  pais: Bloque<RecuentosPais> = bloque(PAIS),
  hora: Bloque<RecuentosHora> = bloque(HORA),
  acotada: { desde: string; hasta: string } | null = null,
) {
  TestBed.configureTestingModule({
    providers: [
      {
        provide: PanelDatosService,
        useValue: {
          porPais: signal(pais),
          porSubregion: signal(bloque(SUBREGION)),
          porHora: signal(hora),
          horaAcotada: signal(acotada),
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(Recuentos);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

describe('Recuentos', () => {
  it('«Sin país asignado» aparece como una categoría más', async () => {
    const { el } = await montar();
    const barras = el.querySelectorAll('section[aria-labelledby="titulo-recuentos-grupo"] g.grafico__barra');
    expect(barras).toHaveLength(2);
    expect(el.querySelector('section[aria-labelledby="titulo-recuentos-grupo"]')?.textContent).toContain('Sin país asignado');
  });

  it('el selector cambia a subregión sin perder «Sin país asignado»', async () => {
    const { fixture, el } = await montar();
    const sel = el.querySelector<HTMLSelectElement>('#agrupacion-recuentos')!;
    sel.value = 'subregion';
    sel.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    const parte = el.querySelector('section[aria-labelledby="titulo-recuentos-grupo"]')!;
    expect(parte.textContent).toContain('Eventos por subregión');
    expect(parte.textContent).toContain('South America');
    expect(parte.textContent).toContain('Sin país asignado');
  });

  it('24 ventanas horarias con 3 en cero se ven todas y se etiquetan como UTC', async () => {
    const { el } = await montar();
    const hora = el.querySelector('section[aria-labelledby="titulo-recuentos-hora"]')!;
    expect(hora.querySelectorAll('g.grafico__barra')).toHaveLength(24);
    expect(hora.querySelectorAll('g[data-tipo="cero"]')).toHaveLength(3);
    expect(hora.textContent).toContain('UTC');
    expect(hora.textContent).toContain('3 sin eventos');
  });

  it('estado vacío con texto claro', async () => {
    const { el } = await montar(bloque<RecuentosPais>({ total: 0, categorias: [] }));
    expect(el.textContent).toContain('No hay eventos que cumplan los filtros actuales.');
  });

  it('error con datos antiguos: los muestra etiquetados', async () => {
    const { el } = await montar(
      bloque(PAIS, {
        estado: 'error',
        error: { tipo: 'servicio_no_disponible', motivo: 'El servicio no está disponible', status: 503, parametro: null },
      }),
    );
    expect(el.textContent).toContain('Datos desactualizados');
    expect(el.textContent).toContain('El servicio no está disponible');
    expect(el.textContent).toContain('Chile');
    expect(el.querySelector('[role="alert"]')).toBeNull();
  });

  it('carga inicial y error sin datos', async () => {
    const cargando = await montar(bloque<RecuentosPais>(null, { estado: 'cargando', lecturaOk: null }));
    expect(cargando.el.textContent).toContain('Cargando datos');
    TestBed.resetTestingModule();
    const fallo = await montar(
      bloque<RecuentosPais>(null, {
        estado: 'error',
        lecturaOk: null,
        error: { tipo: 'red', motivo: 'Sin conexión con la API', status: 0, parametro: null },
      }),
    );
    expect(fallo.el.textContent).toContain('No se pudieron cargar los datos: Sin conexión con la API');
  });

  it('avisa si la ventana horaria se acotó a 31 días', async () => {
    const { el } = await montar(bloque(PAIS), bloque(HORA), {
      desde: '2026-10-02T00:00:00.000Z',
      hasta: '2026-11-02T00:00:00.000Z',
    });
    expect(el.textContent).toContain('supera 31 días');
  });

  it('más de 15 países: el gráfico agrupa el resto y la tabla los lista todos', async () => {
    const muchos: RecuentosPais = {
      total: 400,
      categorias: Array.from({ length: 20 }, (_, i) => ({ codigo: `P${i}`, nombre: `País ${i}`, recuento: 20 - i })),
    };
    const { el } = await montar(bloque(muchos));
    const parte = el.querySelector('section[aria-labelledby="titulo-recuentos-grupo"]')!;
    expect(parte.querySelectorAll('g.grafico__barra')).toHaveLength(16);
    expect(parte.querySelectorAll('details tbody tr')).toHaveLength(20);
  });
});
