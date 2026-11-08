import { Injectable, computed, inject, signal } from '@angular/core';
import { I18nService } from '../i18n/i18n.service';
import {
  CampoFiltro,
  ErroresFiltros,
  FILTROS_VACIOS,
  FiltrosAplicados,
  FiltrosEditados,
  ModoDatos,
  VISTA_VIVO,
  VistaDatos,
  validarFiltros,
} from '../puro/filtros';

export const DEBOUNCE_FILTROS_MS = 400;
export const LIMITE_TABLA_INICIAL = 50;

export interface PaginaTabla {
  limite: number;
  desplazamiento: number;
}

/**
 * Única fuente de filtros del panel (FR-007).
 *  - `editados`: lo que hay en el formulario, tal cual se escribe.
 *  - `aplicados`: lo validado y ya en uso; lo leen mapa, tabla y gráficos.
 * Un cambio válido pasa de editados a aplicados tras 400 ms sin más cambios; uno
 * incoherente se queda en `errores` y NO cambia los aplicados (no llama a la API).
 */
@Injectable({ providedIn: 'root' })
export class FiltrosStore {
  private readonly i18n = inject(I18nService);
  private readonly _editados = signal<FiltrosEditados>({ ...FILTROS_VACIOS });
  private readonly _aplicados = signal<FiltrosAplicados>({});
  private readonly _pagina = signal<PaginaTabla>({
    limite: LIMITE_TABLA_INICIAL,
    desplazamiento: 0,
  });
  private readonly _vista = signal<VistaDatos>({ ...VISTA_VIVO });
  private temporizador: ReturnType<typeof setTimeout> | null = null;

  /**
   * De dónde salen los datos (en directo o REPRODUCCIÓN) y si entran los casos sintéticos.
   * Solo vive en memoria: al recargar vuelve a «en directo» y sin sintéticos (FR-013 de 007).
   */
  readonly vista = this._vista.asReadonly();
  readonly editados = this._editados.asReadonly();
  readonly aplicados = this._aplicados.asReadonly();
  /** Paginación de la tabla (`limite`/`desplazamiento`); vuelve a 0 al cambiar los filtros. */
  readonly pagina = this._pagina.asReadonly();
  /** `event_id` elegido con «Ver en el mapa» (tabla → mapa). */
  readonly eventoSeleccionado = signal<string | null>(null);

  /** Mensajes de validación en el idioma vigente: al cambiarlo se recalculan sin tocar lo escrito. */
  readonly errores = computed<ErroresFiltros>(() => {
    const v = validarFiltros(this._editados(), this.i18n.t());
    return v.ok ? {} : v.errores;
  });
  readonly hayErrores = computed(() => Object.keys(this.errores()).length > 0);
  /** `true` mientras hay cambios editados que aún no se han aplicado. */
  readonly pendiente = computed(() => {
    const v = validarFiltros(this._editados());
    return v.ok && JSON.stringify(v.filtros) !== JSON.stringify(this._aplicados());
  });

  editar(parcial: Partial<FiltrosEditados>): void {
    this._editados.update((f) => ({ ...f, ...parcial }));
    this.cancelarTemporizador();
    this.temporizador = setTimeout(() => {
      this.temporizador = null;
      this.aplicarYa();
    }, DEBOUNCE_FILTROS_MS);
  }

  /** Atajo para un solo campo. */
  editarCampo(campo: CampoFiltro, valor: string): void {
    this.editar({ [campo]: valor });
  }

  /** Aplica sin esperar el debounce. Devuelve `false` si los filtros no son válidos. */
  aplicarYa(): boolean {
    this.cancelarTemporizador();
    const v = validarFiltros(this._editados());
    if (!v.ok) return false;
    if (JSON.stringify(v.filtros) === JSON.stringify(this._aplicados())) return true;
    this._aplicados.set(v.filtros);
    this._pagina.update((p) => ({ ...p, desplazamiento: 0 }));
    return true;
  }

  restablecer(): void {
    this._editados.set({ ...FILTROS_VACIOS });
    this.aplicarYa();
  }

  /** Cambia entre en directo y REPRODUCCIÓN. Instantáneo (no es texto): sin debounce. */
  fijarModo(modo: ModoDatos): void {
    this.cambiarVista({ ...this._vista(), modo });
  }

  /** Activa o apaga los casos de prueba sintéticos. Instantáneo. */
  fijarSinteticos(sinteticos: boolean): void {
    this.cambiarVista({ ...this._vista(), sinteticos });
  }

  /** Otra vista = otro conjunto de eventos: la tabla vuelve a la página 0 y se suelta la selección. */
  private cambiarVista(nueva: VistaDatos): void {
    const actual = this._vista();
    if (actual.modo === nueva.modo && actual.sinteticos === nueva.sinteticos) return;
    this._vista.set(nueva);
    this._pagina.update((p) => (p.desplazamiento === 0 ? p : { ...p, desplazamiento: 0 }));
    this.eventoSeleccionado.set(null);
  }

  irAPagina(desplazamiento: number): void {
    const d = Math.max(0, Math.min(100_000, Math.trunc(desplazamiento)));
    this._pagina.update((p) => (p.desplazamiento === d ? p : { ...p, desplazamiento: d }));
  }

  fijarLimite(limite: number): void {
    const l = Math.max(1, Math.min(500, Math.trunc(limite)));
    this._pagina.set({ limite: l, desplazamiento: 0 });
  }

  private cancelarTemporizador(): void {
    if (this.temporizador !== null) {
      clearTimeout(this.temporizador);
      this.temporizador = null;
    }
  }
}
