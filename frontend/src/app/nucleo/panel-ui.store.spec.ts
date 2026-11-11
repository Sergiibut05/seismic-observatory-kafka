import { TestBed } from '@angular/core/testing';
import { PanelUiStore } from './panel-ui.store';

describe('PanelUiStore', () => {
  it('el plano es el encuadre por defecto y volver a él cierra los filtros', () => {
    const ui = TestBed.inject(PanelUiStore);
    expect(ui.enGlobo()).toBe(false);
    expect(ui.superficie()).toBe('mapa');
    ui.fijarGlobo(true);
    ui.abrirFiltro('pais');
    expect(ui.filtrosAbiertos()).toBe(true);
    ui.fijarGlobo(false);
    expect(ui.enGlobo()).toBe(false);
    expect(ui.filtrosAbiertos()).toBe(false);
    expect(ui.campoFoco()).toBeNull();
  });
});
