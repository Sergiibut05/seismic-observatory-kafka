import { Injectable, computed, signal } from '@angular/core';
import { ErrorPanel, motivoError } from '../puro/errores';
import {
  formatearDecimal,
  formatearEntero,
  formatearHoraConUtc,
  formatearInstanteUtc,
  formatearMagnitud,
  formatearProfundidad,
} from '../puro/formato';
import { Clave } from './es';
import { IDIOMA_POR_DEFECTO, Idioma, ParametrosTraduccion, crearTraductor, esIdioma } from './traducir';

export const CLAVE_IDIOMA = 'idioma';

function leerGuardado(): Idioma {
  try {
    const valor = localStorage.getItem(CLAVE_IDIOMA);
    return esIdioma(valor) ? valor : IDIOMA_POR_DEFECTO;
  } catch {
    return IDIOMA_POR_DEFECTO; // almacenamiento bloqueado: se usa el idioma por defecto
  }
}

/**
 * Idioma del panel (FR-001): una señal con el idioma vigente. Cambiarlo no toca la API: los componentes
 * leen `t()` o `tr()` y se repintan con los datos que ya tienen.
 */
@Injectable({ providedIn: 'root' })
export class I18nService {
  private readonly _idioma = signal<Idioma>(leerGuardado());

  readonly idioma = this._idioma.asReadonly();
  /** Traductor vigente: se pasa a las funciones puras y a quien necesite el idioma de los números. */
  readonly t = computed(() => crearTraductor(this._idioma()));

  constructor() {
    this.aplicarAlDocumento(this._idioma());
  }

  /** Traduce leyendo la señal: usable en plantillas (`i18n.tr('mapa.titulo')`) sin guardar `t()` aparte. */
  tr(clave: Clave, parametros?: ParametrosTraduccion): string {
    return this.t()(clave, parametros);
  }

  /** Cambia de idioma al instante y lo recuerda; no recarga ni pide datos (FR-002). */
  fijar(idioma: Idioma): void {
    if (idioma === this._idioma()) return;
    this._idioma.set(idioma);
    try {
      localStorage.setItem(CLAVE_IDIOMA, idioma);
    } catch {
      // sin almacenamiento el cambio sigue valiendo para esta sesión
    }
    this.aplicarAlDocumento(idioma);
  }

  // Números y fechas con el idioma vigente (FR-004); los instantes siguen siempre en UTC.
  entero(v: number | null | undefined): string {
    return formatearEntero(v, this.t());
  }
  decimal(v: number | null | undefined, maxDecimales: number): string {
    return formatearDecimal(v, maxDecimales, this.t());
  }
  magnitud(v: number | null | undefined): string {
    return formatearMagnitud(v, this.t());
  }
  profundidad(v: number | null | undefined): string {
    return formatearProfundidad(v, this.t());
  }
  instante(iso: string | null | undefined): string {
    return formatearInstanteUtc(iso, this.t());
  }
  horaConUtc(iso: string | null | undefined): string {
    return formatearHoraConUtc(iso, undefined, this.t());
  }
  /**
   * Motivo legible de un error de la API en el idioma vigente. `ErrorPanel.motivo` ya es la frase en español
   * (la que escriben los logs); en inglés se rehace a partir de `tipo`, `status` y `parametro`.
   */
  motivo(error: ErrorPanel | null | undefined): string {
    if (!error) return '';
    return this._idioma() === 'es' ? error.motivo : motivoError(error, this.t());
  }

  private aplicarAlDocumento(idioma: Idioma): void {
    if (typeof document === 'undefined') return;
    document.documentElement.lang = idioma;
    document.title = crearTraductor(idioma)('cabecera.titulo');
  }
}
