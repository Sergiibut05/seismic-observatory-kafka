import { TestBed } from '@angular/core/testing';
import { PanelUiStore, recorteDesde } from './panel-ui.store';

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

describe('recorteDesde', () => {
  it('deja ver solo el marco del mapa, con esquinas redondeadas', () => {
    expect(recorteDesde({ top: 100, right: 900, bottom: 600, left: 300 }, 1000, 800)).toBe(
      'inset(100px 100px 200px 300px round 12px)',
    );
  });
});

describe('PanelUiStore: transición plano ↔ globo', () => {
  /** `startViewTransition` simulado: ejecuta el callback y guarda cuándo termina su promesa. */
  function simular() {
    const doc = document as unknown as { startViewTransition?: unknown };
    const eventos: string[] = [];
    let terminaCallback: Promise<void> | null = null;
    let terminada = false;
    let fin!: () => void;
    const finished = new Promise<void>((ok) => (fin = ok));
    doc.startViewTransition = (cb: () => void | Promise<void>) => {
      eventos.push('transición');
      terminaCallback = Promise.resolve(cb()).then(() => {
        terminada = true;
      });
      return { ready: terminaCallback, finished };
    };
    return {
      eventos,
      terminada: () => terminada,
      esperarCallback: () => terminaCallback,
      acabar: fin,
    };
  }
  const turno = () => new Promise((ok) => setTimeout(ok));

  afterEach(() => {
    delete (document as unknown as { startViewTransition?: unknown }).startViewTransition;
    vi.restoreAllMocks();
  });

  it('al entrar, prepara el globo antes de congelar la página y no revela hasta que avisa', async () => {
    const sim = simular();
    const ui = TestBed.inject(PanelUiStore);
    let precalentado = false;
    ui.precalentarGlobo = async () => {
      sim.eventos.push('precarga');
      precalentado = true;
    };
    ui.fijarGlobo(true);
    expect(ui.enGlobo()).toBe(false); // todavía nada: primero la precarga, con la página viva
    await turno();
    expect(precalentado).toBe(true);
    expect(sim.eventos).toEqual(['precarga', 'transición']); // la precarga va antes de la transición
    expect(ui.enGlobo()).toBe(true);
    await turno();
    expect(sim.terminada()).toBe(false); // el callback espera al globo
    ui.avisarGloboListo();
    await sim.esperarCallback();
    expect(sim.terminada()).toBe(true);
    sim.acabar();
    await turno();
    expect(document.documentElement.classList.contains('vt-globo-entra')).toBe(false);
  });

  it('una precarga que no acaba no bloquea la entrada para siempre', async () => {
    vi.useFakeTimers();
    try {
      const sim = simular();
      const ui = TestBed.inject(PanelUiStore);
      ui.precalentarGlobo = () => new Promise<void>(() => undefined);
      ui.fijarGlobo(true);
      await vi.advanceTimersByTimeAsync(4100);
      expect(sim.eventos).toEqual(['transición']);
      await vi.advanceTimersByTimeAsync(2600); // y el globo tampoco avisa: se revela igualmente
      expect(sim.terminada()).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('al salir, reencuadra el plano dentro de la transición y no espera al globo', async () => {
    const ui = TestBed.inject(PanelUiStore);
    ui.enGlobo.set(true);
    const sim = simular();
    const llamadas: string[] = [];
    ui.capturarVista = () => llamadas.push('capturar');
    ui.prepararPlano = () => llamadas.push(`plano con enGlobo=${ui.enGlobo()}`);
    ui.fijarGlobo(false);
    await turno();
    await sim.esperarCallback();
    expect(llamadas).toEqual(['capturar', 'plano con enGlobo=false']);
    expect(sim.terminada()).toBe(true);
    sim.acabar();
  });

  it('ignora cambios de vista mientras hay una transición en curso', async () => {
    const sim = simular();
    const ui = TestBed.inject(PanelUiStore);
    ui.fijarGlobo(true);
    ui.fijarGlobo(false);
    ui.fijarGlobo(true);
    await turno();
    expect(sim.eventos.filter((e) => e === 'transición')).toHaveLength(1);
    ui.avisarGloboListo();
    await sim.esperarCallback();
    sim.acabar();
    await turno();
    ui.fijarGlobo(false); // ya terminó: vuelve a funcionar
    await turno();
    expect(sim.eventos.filter((e) => e === 'transición')).toHaveLength(2);
    expect(ui.enGlobo()).toBe(false);
  });
});
