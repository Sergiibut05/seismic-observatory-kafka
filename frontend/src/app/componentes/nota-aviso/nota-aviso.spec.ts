import { TestBed } from '@angular/core/testing';
import { NotaAviso } from './nota-aviso';

describe('NotaAviso', () => {
  it('deja claro que no es predicción ni evaluación de riesgo', async () => {
    const fixture = TestBed.createComponent(NotaAviso);
    await fixture.whenStable();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('No predicen terremotos');
    expect(texto).toContain('ni evalúan el riesgo');
  });
});
