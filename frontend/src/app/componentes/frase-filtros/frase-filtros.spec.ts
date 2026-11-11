import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelUiStore } from '../../nucleo/panel-ui.store';
import { FraseFiltros } from './frase-filtros';

describe('FraseFiltros', () => {
  it('un trozo abre el formulario de filtros en el campo correspondiente', () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(FraseFiltros);
    fixture.detectChanges();
    const ui = TestBed.inject(PanelUiStore);
    const el = fixture.nativeElement as HTMLElement;
    const botones = Array.from(el.querySelectorAll<HTMLButtonElement>('.frase__trozo'));
    expect(botones.length).toBe(4);
    botones[2].click();
    fixture.detectChanges();
    expect(ui.filtrosAbiertos()).toBe(true);
    expect(ui.campoFoco()).toBe('pais');
    expect(TestBed.inject(FiltrosStore).aplicados()).toEqual({});
  });
});
