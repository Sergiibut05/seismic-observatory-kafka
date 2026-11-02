import { ColaRefresco } from './cola-refresco';

/** Temporizador manual: el test decide cuándo «pasa» el tiempo. */
class RelojManual {
  ahora = 1_000_000;
  private nextId = 1;
  private tareas = new Map<number, { fn: () => void; en: number }>();

  programar = (fn: () => void, ms: number): unknown => {
    const id = this.nextId++;
    this.tareas.set(id, { fn, en: this.ahora + ms });
    return id;
  };
  cancelar = (id: unknown): void => {
    this.tareas.delete(id as number);
  };
  get pendientes(): number {
    return this.tareas.size;
  }
  avanzar(ms: number): void {
    this.ahora += ms;
    for (const [id, t] of [...this.tareas]) {
      if (t.en <= this.ahora) {
        this.tareas.delete(id);
        t.fn();
      }
    }
  }
}

interface Pendiente {
  terminar: () => void;
  fallar: () => void;
}

function montar(intervaloMs = 60_000) {
  const reloj = new RelojManual();
  const rondas: Pendiente[] = [];
  const ejecutar = vi.fn(
    () =>
      new Promise<void>((resolve, reject) => {
        rondas.push({ terminar: resolve, fallar: () => reject(new Error('fallo')) });
      }),
  );
  const cola = new ColaRefresco(ejecutar, {
    intervaloMs,
    programar: reloj.programar,
    cancelar: reloj.cancelar,
    ahora: () => reloj.ahora,
  });
  return { reloj, rondas, ejecutar, cola };
}

const vaciar = () => new Promise<void>((r) => setTimeout(r, 0));

async function terminarUltima(rondas: Pendiente[]) {
  rondas[rondas.length - 1].terminar();
  await vaciar();
}

describe('ColaRefresco', () => {
  it('pedir() lanza una ronda; con otra en curso no se solapa', async () => {
    const { cola, ejecutar, rondas } = montar();
    cola.pedir();
    expect(ejecutar).toHaveBeenCalledTimes(1);
    expect(cola.enCurso).toBe(true);
    await terminarUltima(rondas);
    expect(cola.enCurso).toBe(false);
    expect(ejecutar).toHaveBeenCalledTimes(1);
  });

  it('dos pedir() durante una ronda → exactamente 1 repetición al terminar', async () => {
    const { cola, ejecutar, rondas } = montar();
    cola.pedir();
    cola.pedir();
    cola.pedir();
    expect(ejecutar).toHaveBeenCalledTimes(1);
    await terminarUltima(rondas); // termina la 1.ª → arranca la repetición
    expect(ejecutar).toHaveBeenCalledTimes(2);
    await terminarUltima(rondas); // termina la repetición → no hay más
    expect(ejecutar).toHaveBeenCalledTimes(2);
  });

  it('el temporizador lanza una ronda cada 60 s tras terminar la anterior', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    await terminarUltima(rondas);
    expect(reloj.pendientes).toBe(1);
    reloj.avanzar(59_000);
    expect(ejecutar).toHaveBeenCalledTimes(1);
    reloj.avanzar(1_000);
    expect(ejecutar).toHaveBeenCalledTimes(2);
  });

  it('un pedir() manual reinicia el reloj de 60 s (sin ronda doble)', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    await terminarUltima(rondas);
    reloj.avanzar(30_000);
    cola.pedir();
    await terminarUltima(rondas);
    reloj.avanzar(45_000); // 75 s desde la primera ronda, pero solo 45 desde la última
    expect(ejecutar).toHaveBeenCalledTimes(2);
    reloj.avanzar(15_000);
    expect(ejecutar).toHaveBeenCalledTimes(3);
  });

  it('una ronda que falla no detiene el ciclo', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    rondas[0].fallar();
    await vaciar();
    expect(cola.enCurso).toBe(false);
    reloj.avanzar(60_000);
    expect(ejecutar).toHaveBeenCalledTimes(2);
  });

  it('pestaña oculta: el temporizador se cancela y no hay rondas', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    await terminarUltima(rondas);
    cola.pausar();
    expect(reloj.pendientes).toBe(0);
    reloj.avanzar(10 * 60_000);
    expect(ejecutar).toHaveBeenCalledTimes(1);
  });

  it('una ronda en curso al ocultar termina y no reprograma', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    cola.pausar();
    await terminarUltima(rondas);
    expect(reloj.pendientes).toBe(0);
    reloj.avanzar(10 * 60_000);
    expect(ejecutar).toHaveBeenCalledTimes(1);
  });

  it('al volver a ser visible: 1 ronda inmediata', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    await terminarUltima(rondas);
    cola.pausar();
    reloj.avanzar(5 * 60_000);
    cola.reanudar();
    expect(ejecutar).toHaveBeenCalledTimes(2);
    await terminarUltima(rondas);
    expect(reloj.pendientes).toBe(1);
  });

  it('al volver, si se acaba de lanzar una ronda, no se repite (solo se reprograma)', async () => {
    const { cola, reloj, ejecutar, rondas } = montar();
    cola.pedir();
    await terminarUltima(rondas);
    cola.pausar();
    reloj.avanzar(1_000);
    cola.reanudar();
    expect(ejecutar).toHaveBeenCalledTimes(1);
    expect(reloj.pendientes).toBe(1);
  });

  it('al volver con una ronda en curso: no se lanza otra', async () => {
    const { cola, ejecutar, rondas } = montar();
    cola.pedir();
    cola.pausar();
    cola.reanudar();
    expect(ejecutar).toHaveBeenCalledTimes(1);
    await terminarUltima(rondas);
  });

  it('reanudar() sin haber pausado no hace nada', () => {
    const { cola, ejecutar } = montar();
    cola.reanudar();
    expect(ejecutar).not.toHaveBeenCalled();
  });

  it('detener() cancela el temporizador', async () => {
    const { cola, reloj, rondas } = montar();
    cola.pedir();
    await terminarUltima(rondas);
    cola.detener();
    expect(reloj.pendientes).toBe(0);
  });
});
