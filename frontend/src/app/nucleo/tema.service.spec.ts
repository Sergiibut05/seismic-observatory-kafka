import { TestBed } from '@angular/core/testing';
import { CLAVE_TEMA, TemaService } from './tema.service';

describe('TemaService', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset['tema'];
  });
  afterEach(() => vi.restoreAllMocks());

  it('por defecto es papel y lo marca en <html>', () => {
    const s = TestBed.inject(TemaService);
    expect(s.tema()).toBe('papel');
    expect(document.documentElement.dataset['tema']).toBe('papel');
  });

  it('respeta lo guardado e ignora valores desconocidos', () => {
    localStorage.setItem(CLAVE_TEMA, 'noche');
    expect(TestBed.inject(TemaService).tema()).toBe('noche');
    TestBed.resetTestingModule();
    localStorage.setItem(CLAVE_TEMA, 'violeta');
    expect(TestBed.inject(TemaService).tema()).toBe('papel');
  });

  it('alternar cambia, guarda y actualiza el documento (sin transición en jsdom)', () => {
    const s = TestBed.inject(TemaService);
    s.alternar({ x: 10, y: 10 });
    expect(s.tema()).toBe('noche');
    expect(localStorage.getItem(CLAVE_TEMA)).toBe('noche');
    expect(document.documentElement.dataset['tema']).toBe('noche');
    s.alternar();
    expect(s.tema()).toBe('papel');
  });

  it('con el almacenamiento bloqueado sigue funcionando en la sesión', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado');
    });
    const s = TestBed.inject(TemaService);
    expect(s.tema()).toBe('papel');
    s.alternar();
    expect(s.tema()).toBe('noche');
  });
});
