import { ApplicationRef, Injectable, inject, signal } from '@angular/core';
import { TEMA_POR_DEFECTO, Tema, esTema } from '../puro/tema';
import { DURACION_TINTA_MS, fotogramasTinta } from '../puro/tinta';

export const CLAVE_TEMA = 'observatorio.tema';

type DocConTransicion = Document & {
  startViewTransition?: (cb: () => void) => { finished: Promise<void>; ready: Promise<void> };
};

function leerGuardado(): Tema {
  try {
    const v = localStorage.getItem(CLAVE_TEMA);
    return esTema(v) ? v : TEMA_POR_DEFECTO;
  } catch {
    return TEMA_POR_DEFECTO;
  }
}

/**
 * Tema papel / noche (011). `index.html` ya pone `data-tema` antes del primer pintado; este
 * servicio lo mantiene, lo guarda y anima el cambio con la gota de tinta.
 */
@Injectable({ providedIn: 'root' })
export class TemaService {
  readonly tema = signal<Tema>(leerGuardado());
  private readonly appRef = inject(ApplicationRef);
  private enCurso = false;

  constructor() {
    this.ponerEnDocumento(this.tema());
  }

  fijar(tema: Tema): void {
    this.tema.set(tema);
    this.ponerEnDocumento(tema);
    try {
      localStorage.setItem(CLAVE_TEMA, tema);
    } catch {
      // Almacenamiento bloqueado: el tema vale para esta sesión.
    }
  }

  /** Cambia de tema; la tinta nace en `origen` (el botón), en píxeles de la ventana. */
  alternar(origen?: { x: number; y: number }): void {
    const nuevo: Tema = this.tema() === 'papel' ? 'noche' : 'papel';
    const doc = typeof document === 'undefined' ? null : (document as DocConTransicion);
    const reducido =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!doc?.startViewTransition || reducido || this.enCurso) {
      this.fijar(nuevo);
      return;
    }

    // A noche, la tinta se derrama desde el botón sobre el papel; a papel, se recoge hacia él.
    const derrama = nuevo === 'noche';
    const raiz = doc.documentElement;
    const x = origen?.x ?? innerWidth;
    const y = origen?.y ?? 0;
    const fotogramas = fotogramasTinta({
      ancho: innerWidth,
      alto: innerHeight,
      x,
      y,
      semilla: Date.now(),
    });
    // Todo entra en la instantánea raíz: sin esto, cabecera y mapa harían su propia transición.
    const clase = derrama ? 'tema-derrama' : 'tema-recoge';
    raiz.style.setProperty('--tinta-x', `${Math.round(x)}px`);
    raiz.style.setProperty('--tinta-y', `${Math.round(y)}px`);
    raiz.classList.add('cambiando-tema', clase);
    this.enCurso = true;
    const transicion = doc.startViewTransition(() => {
      this.fijar(nuevo);
      this.appRef.tick();
    });
    let gota: Animation | null = null;
    transicion.ready
      .then(() => {
        gota = raiz.animate(
          { clipPath: derrama ? fotogramas : [...fotogramas].reverse() },
          {
            duration: DURACION_TINTA_MS,
            // El ritmo ya va en los fotogramas (al recoger, invertido: acelera hacia el botón).
            easing: 'linear',
            fill: 'both',
            pseudoElement: derrama ? '::view-transition-new(root)' : '::view-transition-old(root)',
          },
        );
      })
      .catch(() => undefined);
    transicion.finished.finally(() => {
      // Con `fill: both` la animación seguiría viva sobre un pseudoelemento que ya no existe.
      gota?.cancel();
      raiz.classList.remove('cambiando-tema', clase);
      raiz.style.removeProperty('--tinta-x');
      raiz.style.removeProperty('--tinta-y');
      this.enCurso = false;
    });
  }

  private ponerEnDocumento(tema: Tema): void {
    if (typeof document === 'undefined') return;
    document.documentElement.dataset['tema'] = tema;
  }
}
