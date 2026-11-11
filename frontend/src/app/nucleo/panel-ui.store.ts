import { ApplicationRef, Injectable, inject, signal } from '@angular/core';
import { CampoFiltro } from '../puro/filtros';
import { VISTA_MUNDO_INICIAL, VistaMundo } from '../puro/mundo';

type DocConTransicion = Document & {
  startViewTransition?: (cb: () => void | Promise<void>) => {
    finished: Promise<void>;
    ready: Promise<void>;
  };
};

const DURACION_RECORTE_MS = 520;
/** Lo máximo que se espera a la precarga del globo antes de empezar (red lenta: se abre igualmente). */
const ESPERA_PRECARGA_MS = 4000;
/** Lo máximo que se mantiene congelada la página vieja esperando a que el globo esté listo. */
const ESPERA_ESCENA_MS = 2500;

const esperar = (ms: number) => new Promise<void>((ok) => setTimeout(ok, ms));

/** `clip-path` que deja ver solo el rectángulo del marco del mapa (con sus esquinas). */
export function recorteDesde(
  r: { top: number; right: number; bottom: number; left: number },
  ancho: number,
  alto: number,
): string {
  const px = (n: number) => `${Math.round(n)}px`;
  return `inset(${px(r.top)} ${px(ancho - r.right)} ${px(alto - r.bottom)} ${px(r.left)} round 12px)`;
}

export type SuperficiePanel = 'mapa' | 'tabla' | 'analisis';
export type CampoFoco = CampoFiltro | 'modo';

/**
 * Encuadre del panel (010): globo a sangre, superficie móvil y diálogo de filtros.
 * No toca los filtros aplicados ni pide datos.
 */
@Injectable({ providedIn: 'root' })
export class PanelUiStore {
  readonly enGlobo = signal(false);
  readonly superficie = signal<SuperficiePanel>('mapa');
  readonly filtrosAbiertos = signal(false);
  readonly campoFoco = signal<CampoFoco | null>(null);
  /**
   * Último centro y zoom que se miraba (plano o globo). No es una señal: se escribe en cada
   * movimiento de cámara y solo se lee al cambiar de modo.
   */
  vistaMundo: Omit<VistaMundo, 'zoom'> & { zoom: number | null } = { ...VISTA_MUNDO_INICIAL };
  /** Lo registra el globo mientras vive: vuelca su cámara en `vistaMundo` (el giro automático no avisa). */
  capturarVista: (() => void) | null = null;
  /** Lo registra el plano: empieza a preparar el globo (módulos, fronteras y textura) y avisa al acabar. */
  precalentarGlobo: (() => Promise<void>) | null = null;
  /** Lo registra el plano: se reencuadra y se redimensiona de forma síncrona, antes de que se vea. */
  prepararPlano: (() => void) | null = null;
  private resolverGloboListo: (() => void) | null = null;
  private enCurso = false;

  private readonly appRef = inject(ApplicationRef);

  /** El globo avisa de que ya tiene textura, columnas y cámara (o de que no va a poder tenerlas). */
  avisarGloboListo(): void {
    this.resolverGloboListo?.();
    this.resolverGloboListo = null;
  }

  fijarGlobo(activo: boolean): void {
    if (activo === this.enGlobo() || this.enCurso) return;
    if (!activo) this.capturarVista?.();
    const aplicar = () => {
      this.enGlobo.set(activo);
      if (!activo) this.cerrarFiltros();
    };
    const doc = typeof document === 'undefined' ? null : (document as DocConTransicion);
    const reducido =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!doc?.startViewTransition || reducido) {
      aplicar();
      return;
    }
    this.enCurso = true;
    // 1. Antes de congelar nada: lo pesado del globo se prepara con la página viva.
    //    Normalmente ya está hecho (el plano lo precalienta en un momento de calma).
    const raiz = doc.documentElement;
    let preparado: Promise<unknown> = Promise.resolve();
    if (activo) {
      raiz.classList.add('preparando-globo');
      preparado = Promise.race([
        this.precalentarGlobo?.() ?? Promise.resolve(),
        esperar(ESPERA_PRECARGA_MS),
      ]);
    }
    void preparado
      .catch(() => undefined)
      .then(() => {
        raiz.classList.remove('preparando-globo');
        this.transicionar(doc, activo, aplicar);
      });
  }

  /**
   * 2. Recorte, no fundido. Al entrar, la escena se descubre desde el marco del mapa hasta llenar la
   * ventana; al salir, se encoge hacia el marco. Lo de debajo no se mueve, así que no hay doble
   * exposición ni una foto del mapa estirada.
   *
   * La página vieja se queda quieta hasta que el estado nuevo está completo: al entrar, hasta que el
   * globo tiene textura y columnas; al salir, hasta que el plano ha recuperado su tamaño y su
   * encuadre. Así lo que se revela nunca está a medias (y no «salta» después).
   */
  private transicionar(doc: DocConTransicion, activo: boolean, aplicar: () => void): void {
    const raiz = doc.documentElement;
    const marco = () =>
      doc.querySelector('.mapa-bloque .mapa-marco')?.getBoundingClientRect() ?? null;
    let rect = activo ? marco() : null;
    const clase = activo ? 'vt-globo-entra' : 'vt-globo-sale';
    raiz.classList.add(clase);
    // Hasta que arranca la animación, la escena nueva ya nace recortada (si no, habría un fotograma a pantalla completa).
    if (rect)
      raiz.style.setProperty('--recorte-inicial', recorteDesde(rect, innerWidth, innerHeight));
    const limpiar = () => {
      raiz.classList.remove(clase);
      raiz.style.removeProperty('--recorte-inicial');
      this.resolverGloboListo = null;
      this.enCurso = false;
    };
    let transicion: ReturnType<NonNullable<DocConTransicion['startViewTransition']>>;
    try {
      transicion = doc.startViewTransition!(async () => {
        const escena = activo
          ? new Promise<void>((ok) => {
              this.resolverGloboListo = ok;
            })
          : null;
        aplicar();
        this.appRef.tick();
        if (!activo) {
          this.prepararPlano?.();
          rect = marco();
        }
        if (escena) await Promise.race([escena, esperar(ESPERA_ESCENA_MS)]);
      });
    } catch {
      aplicar();
      limpiar();
      return;
    }
    transicion.ready
      .then(() => {
        if (!rect) return;
        const desde = recorteDesde(rect, innerWidth, innerHeight);
        const hasta = 'inset(0px 0px 0px 0px round 0px)';
        raiz.animate(
          { clipPath: activo ? [desde, hasta] : [hasta, desde] },
          {
            duration: DURACION_RECORTE_MS,
            easing: 'cubic-bezier(0.22, 0.8, 0.2, 1)',
            fill: 'both',
            pseudoElement: activo ? '::view-transition-new(root)' : '::view-transition-old(root)',
          },
        );
      })
      .catch(() => undefined);
    transicion.finished.finally(limpiar);
  }

  fijarSuperficie(s: SuperficiePanel): void {
    this.superficie.set(s);
  }

  abrirFiltro(campo: CampoFoco): void {
    this.campoFoco.set(campo);
    this.filtrosAbiertos.set(true);
  }

  cerrarFiltros(): void {
    this.filtrosAbiertos.set(false);
    this.campoFoco.set(null);
  }
}
