import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { RefrescoService } from '../../nucleo/refresco.service';
import { aQuery } from '../../puro/filtros';
import { Filtros } from './filtros';

function montar() {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting()],
  });
  const store = TestBed.inject(FiltrosStore);
  const datos = TestBed.inject(PanelDatosService);
  datos.opcionesPais.set({
    estado: 'ok',
    lecturaOk: 1,
    error: null,
    datos: {
      total: 3,
      categorias: [
        { codigo: 'USA', nombre: 'Estados Unidos', recuento: 2 },
        { codigo: null, nombre: 'Sin país asignado', recuento: 1 },
        { codigo: 'MEX', nombre: 'México', recuento: 1 },
      ],
    },
  });
  const fixture = TestBed.createComponent(Filtros);
  fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  return { fixture, store, el };
}

function escribir(fixture: { detectChanges(): void }, el: HTMLElement, id: string, valor: string) {
  const campo = el.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!;
  campo.value = valor;
  campo.dispatchEvent(new Event(campo instanceof HTMLSelectElement ? 'change' : 'input'));
  fixture.detectChanges();
}

describe('Filtros', () => {
  it('un rango de fechas incoherente muestra el error accesible y no cambia los filtros aplicados', () => {
    const { fixture, store, el } = montar();
    escribir(fixture, el, 'campo-desde', '2026-03-10T00:00');
    escribir(fixture, el, 'campo-hasta', '2026-03-01T00:00');

    const hasta = el.querySelector<HTMLInputElement>('#campo-hasta')!;
    const error = el.querySelector('#error-hasta');
    expect(error?.textContent).toContain('posterior');
    expect(hasta.getAttribute('aria-invalid')).toBe('true');
    expect(hasta.getAttribute('aria-describedby')).toContain('error-hasta');

    const aplicados = store.aplicados();
    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    fixture.detectChanges();
    expect(store.aplicados()).toBe(aplicados);
  });

  it('magnitud mínima mayor que la máxima se rechaza junto al campo', () => {
    const { fixture, el } = montar();
    escribir(fixture, el, 'campo-magnitudMin', '6');
    escribir(fixture, el, 'campo-magnitudMax', '4');
    expect(el.querySelector('#error-magnitudMax')?.textContent).toContain('no puede ser menor');
  });

  it('«Sin país asignado» se serializa tal cual al pulsar Aplicar', () => {
    const { fixture, store, el } = montar();
    escribir(fixture, el, 'campo-pais', 'Sin país asignado');
    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    fixture.detectChanges();
    expect(store.aplicados().pais).toBe('Sin país asignado');
    expect(aQuery(store.aplicados(), 'completo')).toBe('pais=Sin+pa%C3%ADs+asignado');
  });

  it('Aplicar sin cambios pide una ronda ya (p. ej., al volver la API)', () => {
    const { el } = montar();
    const refresco = TestBed.inject(RefrescoService);
    const pedir = vi.spyOn(refresco, 'refrescarAhora').mockImplementation(() => undefined);
    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    expect(pedir).toHaveBeenCalledTimes(1);
  });

  it('Aplicar con filtros nuevos no pide una ronda extra (la lanza el cambio de filtros)', () => {
    const { fixture, el } = montar();
    const refresco = TestBed.inject(RefrescoService);
    const pedir = vi.spyOn(refresco, 'refrescarAhora').mockImplementation(() => undefined);
    escribir(fixture, el, 'campo-magnitudMin', '4');
    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    expect(pedir).not.toHaveBeenCalled();
  });

  it('ofrece los países del catálogo y «Sin país asignado» siempre', () => {
    const { el } = montar();
    const textos = Array.from(el.querySelectorAll('#campo-pais option')).map((o) => o.textContent?.trim());
    expect(textos).toEqual(['Todos los países', 'Sin país asignado', 'Estados Unidos', 'México']);
  });

  it('Restablecer vacía el formulario y los filtros aplicados', () => {
    const { fixture, store, el } = montar();
    escribir(fixture, el, 'campo-magnitudMin', '4,5');
    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    expect(store.aplicados().magnitudMin).toBe(4.5);

    const botones = Array.from(el.querySelectorAll<HTMLButtonElement>('button'));
    botones.find((b) => b.textContent?.includes('Restablecer'))!.click();
    fixture.detectChanges();
    expect(store.aplicados()).toEqual({});
    expect(el.querySelector<HTMLInputElement>('#campo-magnitudMin')!.value).toBe('');
  });

  it('la nota de origen de los datos sigue a la vista (007)', () => {
    const { fixture, store, el } = montar();
    const nota = () => el.querySelector('form > .bloque__nota')?.textContent?.replace(/\s+/g, ' ') ?? '';
    expect(nota()).toContain('Solo se muestran eventos reales.');

    store.fijarSinteticos(true);
    fixture.detectChanges();
    expect(nota()).toContain('casos de prueba sintéticos');
    expect(nota()).not.toContain('Solo se muestran eventos reales');

    store.fijarModo('replay');
    fixture.detectChanges();
    expect(nota()).toContain('REPRODUCCIÓN');

    store.fijarSinteticos(false);
    store.fijarModo('live');
    fixture.detectChanges();
    expect(nota()).toContain('Solo se muestran eventos reales.');
  });

  it('la nota conserva lo de la comparación histórica', () => {
    const { el } = montar();
    expect(el.querySelector('form > .bloque__nota')?.textContent).toContain('La comparación histórica');
  });

  it('el formulario de filtros no tiene control de sintéticos (está en «Datos») y las fechas se rotulan en UTC', () => {
    const { el } = montar();
    expect(el.querySelector('input[type="checkbox"]')).toBeNull();
    expect(el.textContent?.toLowerCase()).not.toContain('sintétic');
    expect(el.querySelector('label[for="campo-desde"]')?.textContent).toContain('UTC');
    expect(el.querySelector('label[for="campo-hasta"]')?.textContent).toContain('UTC');
  });
});
