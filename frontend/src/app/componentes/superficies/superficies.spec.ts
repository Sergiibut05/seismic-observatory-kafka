import { TestBed } from '@angular/core/testing';
import { PanelUiStore } from '../../nucleo/panel-ui.store';
import { Superficies } from './superficies';

describe('Superficies', () => {
  it('cambia la superficie sin tocar el globo', () => {
    const fixture = TestBed.createComponent(Superficies);
    fixture.detectChanges();
    const ui = TestBed.inject(PanelUiStore);
    const el = fixture.nativeElement as HTMLElement;
    const botones = Array.from(el.querySelectorAll<HTMLButtonElement>('.superficies__boton'));
    expect(botones[0].getAttribute('aria-pressed')).toBe('true');
    botones[1].click();
    fixture.detectChanges();
    expect(ui.superficie()).toBe('tabla');
    expect(ui.enGlobo()).toBe(false);
  });
});
