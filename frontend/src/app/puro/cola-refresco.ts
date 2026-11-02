// Cola de refresco: una sola ronda a la vez, como mucho una repetición anotada,
// ciclo de 60 s y pausa con la pestaña oculta. Sin Angular; temporizador y reloj inyectables.

export interface OpcionesCola {
  intervaloMs?: number;
  programar?: (fn: () => void, ms: number) => unknown;
  cancelar?: (manejador: unknown) => void;
  ahora?: () => number;
  /** Si al volver a ser visible se lanzó una ronda hace menos de esto, no se repite. */
  margenReanudarMs?: number;
}

export class ColaRefresco {
  private readonly intervaloMs: number;
  private readonly programar: (fn: () => void, ms: number) => unknown;
  private readonly cancelar: (manejador: unknown) => void;
  private readonly ahora: () => number;
  private readonly margenReanudarMs: number;

  private visible = true;
  private ejecutando = false;
  private pendiente = false;
  private temporizador: unknown = null;
  private ultimoInicio = Number.NEGATIVE_INFINITY;

  constructor(
    private readonly ejecutar: () => Promise<void>,
    opciones: OpcionesCola = {},
  ) {
    this.intervaloMs = opciones.intervaloMs ?? 60_000;
    this.programar = opciones.programar ?? ((fn, ms) => setTimeout(fn, ms));
    this.cancelar = opciones.cancelar ?? ((m) => clearTimeout(m as ReturnType<typeof setTimeout>));
    this.ahora = opciones.ahora ?? (() => Date.now());
    this.margenReanudarMs = opciones.margenReanudarMs ?? 5_000;
  }

  get enCurso(): boolean {
    return this.ejecutando;
  }

  /** Pide una ronda: si ya hay una en curso se anota una sola repetición. */
  pedir(): void {
    this.cancelarTemporizador();
    if (this.ejecutando) {
      this.pendiente = true;
      return;
    }
    this.lanzar();
  }

  /** Pestaña oculta: sin temporizador. Una ronda en curso termina sin reprogramar. */
  pausar(): void {
    this.visible = false;
    this.cancelarTemporizador();
  }

  /** Pestaña visible de nuevo: una ronda inmediata, salvo que acabe de lanzarse otra. */
  reanudar(): void {
    if (this.visible) return;
    this.visible = true;
    if (this.ejecutando) return;
    if (this.ahora() - this.ultimoInicio < this.margenReanudarMs) {
      this.programarSiguiente();
      return;
    }
    this.pedir();
  }

  detener(): void {
    this.pendiente = false;
    this.cancelarTemporizador();
  }

  private lanzar(): void {
    this.ejecutando = true;
    this.ultimoInicio = this.ahora();
    // Un fallo de la ronda no debe romper el ciclo: cada bloque ya registra su error.
    this.ejecutar()
      .catch(() => undefined)
      .finally(() => {
        this.ejecutando = false;
        if (this.pendiente) {
          this.pendiente = false;
          this.lanzar();
          return;
        }
        this.programarSiguiente();
      });
  }

  private programarSiguiente(): void {
    this.cancelarTemporizador();
    if (!this.visible) return;
    this.temporizador = this.programar(() => {
      this.temporizador = null;
      this.pedir();
    }, this.intervaloMs);
  }

  private cancelarTemporizador(): void {
    if (this.temporizador !== null) {
      this.cancelar(this.temporizador);
      this.temporizador = null;
    }
  }
}
