import { Component, computed, inject } from '@angular/core';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { RefrescoService } from '../../nucleo/refresco.service';
import { CampoFiltro, SIN_PAIS, notaOrigenDatos } from '../../puro/filtros';
import { formatearInstanteUtc } from '../../puro/formato';

interface CampoTexto {
  clave: CampoFiltro;
  etiqueta: string;
  tipo: 'datetime-local' | 'text';
  ayuda: string;
}

export interface OpcionSelector {
  valor: string;
  texto: string;
}

const CAMPOS: readonly CampoTexto[] = [
  { clave: 'desde', etiqueta: 'Desde (UTC)', tipo: 'datetime-local', ayuda: 'Fecha y hora en UTC, no en hora local.' },
  { clave: 'hasta', etiqueta: 'Hasta (UTC)', tipo: 'datetime-local', ayuda: 'Debe ser posterior a «Desde».' },
  { clave: 'magnitudMin', etiqueta: 'Magnitud mínima', tipo: 'text', ayuda: 'Entre −10 y 10, p. ej. 4,5.' },
  { clave: 'magnitudMax', etiqueta: 'Magnitud máxima', tipo: 'text', ayuda: 'No menor que la mínima.' },
];

/** Formulario de filtros (FR-002, FR-007). Escribe en `FiltrosStore`; nunca llama a la API. */
@Component({
  selector: 'app-filtros',
  templateUrl: './filtros.html',
  styleUrl: './filtros.css',
})
export class Filtros {
  protected readonly store = inject(FiltrosStore);
  private readonly datos = inject(PanelDatosService);
  private readonly refresco = inject(RefrescoService);

  protected readonly campos = CAMPOS;
  protected readonly editados = this.store.editados;
  /** Qué eventos se muestran: solo reales, sintéticos incluidos o REPRODUCCIÓN. */
  protected readonly nota = computed(() => notaOrigenDatos(this.store.vista()));
  protected readonly errores = this.store.errores;

  /** Países del catálogo con eventos (de `/recuentos/pais` sin filtros) y «Sin país asignado». */
  protected readonly opcionesPais = computed<OpcionSelector[]>(() => {
    const categorias = this.datos.opcionesPais().datos?.categorias ?? [];
    const lista = categorias
      .filter((c) => c.codigo !== null)
      .map((c) => ({ valor: c.codigo as string, texto: c.nombre }))
      .sort((a, b) => a.texto.localeCompare(b.texto, 'es'));
    return [{ valor: SIN_PAIS, texto: SIN_PAIS }, ...lista];
  });

  protected readonly opcionesSubregion = computed<OpcionSelector[]>(() => {
    const categorias = this.datos.opcionesSubregion().datos?.categorias ?? [];
    const nombres = categorias.map((c) => c.nombre).filter((n) => n !== SIN_PAIS);
    nombres.sort((a, b) => a.localeCompare(b, 'es'));
    return [SIN_PAIS, ...nombres].map((n) => ({ valor: n, texto: n }));
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
    return v ? `${formatearInstanteUtc(v.desde)} – ${formatearInstanteUtc(v.hasta)}` : null;
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
}
