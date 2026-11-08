import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { VistaDatos } from './vista-datos';

async function montar() {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  const fixture = TestBed.createComponent(VistaDatos);
  await fixture.whenStable();
  const el = fixture.nativeElement as HTMLElement;
  return { fixture, el, store: TestBed.inject(FiltrosStore) };
}

const radio = (el: HTMLElement, valor: string) =>
  el.querySelector<HTMLInputElement>(`input[type="radio"][value="${valor}"]`)!;
const interruptor = (el: HTMLElement) =>
  el.querySelector<HTMLInputElement>('input[type="checkbox"][role="switch"]')!;
const franjaReplay = (el: HTMLElement) => el.querySelector('.franja--replay');
const avisoSinteticos = (el: HTMLElement) => el.querySelector('.franja--sinteticos');

describe('VistaDatos', () => {
  it('al arrancar: «En directo» marcado, interruptor apagado, sin franja ni aviso', async () => {
    const { el } = await montar();
    expect(radio(el, 'live').checked).toBe(true);
    expect(radio(el, 'replay').checked).toBe(false);
    expect(interruptor(el).checked).toBe(false);
    expect(franjaReplay(el)).toBeNull();
    expect(avisoSinteticos(el)).toBeNull();
    expect(el.querySelector('[role="status"]')).toBeNull();
  });

  it('el selector se llama «Datos» y ofrece «En directo» y «REPRODUCCIÓN»', async () => {
    const { el } = await montar();
    const grupo = el.querySelector('fieldset');
    expect(grupo?.querySelector('legend')?.textContent?.trim()).toBe('Datos');
    const etiquetas = Array.from(grupo!.querySelectorAll('label')).map((l) => l.textContent?.trim());
    expect(etiquetas).toEqual(['En directo', 'REPRODUCCIÓN']);
  });

  it('elegir REPRODUCCIÓN muestra la franja con role="status" y cambia el modo del store', async () => {
    const { fixture, el, store } = await montar();
    radio(el, 'replay').click();
    await fixture.whenStable();
    expect(store.vista().modo).toBe('replay');
    const franja = franjaReplay(el);
    expect(franja).not.toBeNull();
    expect(franja?.getAttribute('role')).toBe('status');
    expect(franja?.textContent).toContain('REPRODUCCIÓN');
    expect(franja?.textContent).toContain('no son datos en directo');
    expect(radio(el, 'replay').checked).toBe(true);
  });

  it('volver a «En directo» quita la franja', async () => {
    const { fixture, el, store } = await montar();
    radio(el, 'replay').click();
    await fixture.whenStable();
    radio(el, 'live').click();
    await fixture.whenStable();
    expect(store.vista().modo).toBe('live');
    expect(franjaReplay(el)).toBeNull();
  });

  it('encender el interruptor muestra el aviso permanente de sintéticos; apagarlo lo quita', async () => {
    const { fixture, el, store } = await montar();
    interruptor(el).click();
    await fixture.whenStable();
    expect(store.vista().sinteticos).toBe(true);
    const aviso = avisoSinteticos(el);
    expect(aviso).not.toBeNull();
    expect(aviso?.getAttribute('role')).toBe('status');
    expect(aviso?.textContent).toContain('Casos de prueba sintéticos incluidos');
    expect(aviso?.textContent).toContain('no son terremotos reales');

    interruptor(el).click();
    await fixture.whenStable();
    expect(store.vista().sinteticos).toBe(false);
    expect(avisoSinteticos(el)).toBeNull();
  });

  it('el aviso de sintéticos y la franja conviven (REPRODUCCIÓN + sintéticos)', async () => {
    const { fixture, el, store } = await montar();
    store.fijarModo('replay');
    store.fijarSinteticos(true);
    await fixture.whenStable();
    expect(franjaReplay(el)).not.toBeNull();
    expect(avisoSinteticos(el)).not.toBeNull();
  });

  it('refleja cambios hechos desde fuera del componente (store)', async () => {
    const { fixture, el, store } = await montar();
    store.fijarModo('replay');
    store.fijarSinteticos(true);
    await fixture.whenStable();
    expect(radio(el, 'replay').checked).toBe(true);
    expect(interruptor(el).checked).toBe(true);
  });

  it('se maneja con teclado: controles nativos, enfocables y con nombre accesible', async () => {
    const { el } = await montar();
    const controles = Array.from(el.querySelectorAll<HTMLInputElement>('input'));
    expect(controles.length).toBe(3);
    for (const c of controles) {
      expect(c.disabled).toBe(false);
      expect(c.tabIndex).toBeGreaterThanOrEqual(0);
      const etiqueta = el.querySelector(`label[for="${c.id}"]`);
      expect(etiqueta, c.id).not.toBeNull();
      expect(etiqueta?.textContent?.trim().length).toBeGreaterThan(0);
    }
    expect(el.querySelector('label[for="vista-sinteticos"]')?.textContent).toContain(
      'Incluir casos de prueba sintéticos',
    );
    // Los dos radios comparten `name`: las flechas mueven la elección dentro del grupo.
    expect(radio(el, 'live').name).toBe(radio(el, 'replay').name);
  });

  it('el interruptor se describe con su ayuda (aria-describedby apunta a un texto que existe)', async () => {
    const { el } = await montar();
    const id = interruptor(el).getAttribute('aria-describedby');
    expect(id).toBeTruthy();
    expect(el.querySelector(`#${id}`)?.textContent).toContain('Apagado por defecto');
  });

  it('no persiste nada en el navegador', async () => {
    const { fixture, el } = await montar();
    radio(el, 'replay').click();
    interruptor(el).click();
    await fixture.whenStable();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
