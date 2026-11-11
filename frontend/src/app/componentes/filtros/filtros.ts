import { Component, computed, effect, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { Clave } from '../../i18n/es';
import { localeDe } from '../../i18n/traducir';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelUiStore } from '../../nucleo/panel-ui.store';
import { RefrescoService } from '../../nucleo/refresco.service';
import { CampoFiltro, ModoDatos, SIN_PAIS, nombreVisible, notaOrigenDatos } from '../../puro/filtros';

interface CampoTexto {
  clave: CampoFiltro;
  etiqueta: Clave;
  tipo: 'datetime-local' | 'text';
  ayuda: Clave;
}

export interface OpcionSelector {
  valor: string;
  texto: string;
}

const CAMPOS: readonly CampoTexto[] = [
  { clave: 'desde', etiqueta: 'filtros.desde', tipo: 'datetime-local', ayuda: 'filtros.desde_ayuda' },
  { clave: 'hasta', etiqueta: 'filtros.hasta', tipo: 'datetime-local', ayuda: 'filtros.hasta_ayuda' },
  { clave: 'magnitudMin', etiqueta: 'filtros.magnitud_min', tipo: 'text', ayuda: 'filtros.magnitud_min_ayuda' },
  { clave: 'magnitudMax', etiqueta: 'filtros.magnitud_max', tipo: 'text', ayuda: 'filtros.magnitud_max_ayuda' },
];

/** Formulario de filtros (FR-002, FR-007). Escribe en `FiltrosStore`; nunca llama a la API. */
@Component({
  selector: 'app-filtros',
  templateUrl: './filtros.html',
  styleUrl: './filtros.css',
})
export class Filtros {
  protected readonly store = inject(FiltrosStore);
  protected readonly ui = inject(PanelUiStore);
  protected readonly i18n = inject(I18nService);
  private readonly datos = inject(PanelDatosService);
  private readonly refresco = inject(RefrescoService);

  constructor() {
    effect(() => {
      const campo = this.ui.campoFoco();
      const abiertos = this.ui.filtrosAbiertos();
      if (!abiertos || !campo) return;
      const id =
        campo === 'modo'
          ? this.store.vista().modo === 'replay'
            ? 'filtro-modo-replay'
            : 'filtro-modo-live'
          : `campo-${campo}`;
      queueMicrotask(() => document.getElementById(id)?.focus());
    });
  }

  protected readonly campos = CAMPOS;
  protected readonly editados = this.store.editados;
  /** Qué eventos se muestran: solo reales, sintéticos incluidos o REPRODUCCIÓN. */
  protected readonly nota = computed(() => notaOrigenDatos(this.store.vista(), this.i18n.t()));
  protected readonly errores = this.store.errores;

  /**
   * Países del catálogo con eventos (de `/recuentos/pais` sin filtros) y «Sin país asignado».
   * El `valor` es lo que viaja a la API; el `texto` sigue el idioma (los nombres del catálogo no se traducen).
   */
  protected readonly opcionesPais = computed<OpcionSelector[]>(() => {
    const t = this.i18n.t();
    const categorias = this.datos.opcionesPais().datos?.categorias ?? [];
    const lista = categorias
      .filter((c) => c.codigo !== null)
      .map((c) => ({ valor: c.codigo as string, texto: c.nombre }))
      .sort((a, b) => a.texto.localeCompare(b.texto, localeDe(t.idioma)));
    return [{ valor: SIN_PAIS, texto: nombreVisible(SIN_PAIS, t) }, ...lista];
  });

  protected readonly opcionesSubregion = computed<OpcionSelector[]>(() => {
    const t = this.i18n.t();
    const categorias = this.datos.opcionesSubregion().datos?.categorias ?? [];
    const nombres = categorias.map((c) => c.nombre).filter((n) => n !== SIN_PAIS);
    nombres.sort((a, b) => a.localeCompare(b, localeDe(t.idioma)));
    return [SIN_PAIS, ...nombres].map((n) => ({ valor: n, texto: nombreVisible(n, t) }));
  });

  protected readonly opcionesCargando = computed(
    () =>
      this.datos.opcionesPais().datos === null && this.datos.opcionesPais().error === null,
  );
  protected readonly opcionesError = computed(
    () => this.datos.opcionesPais().error ?? this.datos.opcionesSubregion().error,
  );

  /** Si el recuento por hora se acotó a 31 días, ventana que se está usando. */
  protected readonly horaAcotada = computed(() => {
    const v = this.datos.horaAcotada();
    return v ? `${this.i18n.instante(v.desde)} – ${this.i18n.instante(v.hasta)}` : null;
  });

  protected editar(clave: CampoFiltro, evento: Event): void {
    this.store.editarCampo(clave, (evento.target as HTMLInputElement | HTMLSelectElement).value);
  }

  /** Ids que describen el campo: la ayuda y, si hay, el error. */
  protected descripcion(clave: CampoFiltro): string {
    return this.errores()[clave] ? `ayuda-${clave} error-${clave}` : `ayuda-${clave}`;
  }

  /** Con los mismos filtros no hay cambio que dispare la ronda: se pide a mano (p. ej., al volver la API). */
  protected aplicar(evento: Event): void {
    evento.preventDefault();
    const antes = this.store.aplicados();
    if (this.store.aplicarYa() && this.store.aplicados() === antes) this.refresco.refrescarAhora();
  }

  protected restablecer(): void {
    this.store.restablecer();
  }

  protected elegirModo(modo: ModoDatos): void {
    this.store.fijarModo(modo);
  }

  protected alternarSinteticos(evento: Event): void {
    this.store.fijarSinteticos((evento.target as HTMLInputElement).checked);
  }
}
