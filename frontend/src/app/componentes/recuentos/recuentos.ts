import { Component, computed, inject, signal } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import {
  DatoBarra,
  etiquetaHoraUtc,
  etiquetaVentanaUtc,
  principalesConResto,
} from '../../puro/barras';
import { SIN_PAIS, nombreVisible } from '../../puro/filtros';
import { AvisoBloque } from '../grafico-barras/aviso-bloque';
import { formatearDecimal } from '../../puro/formato';
import { GraficoBarras, Referencia } from '../grafico-barras/grafico-barras';

export type Agrupacion = 'pais' | 'subregion';

const MAX_BARRAS = 15;

/** Recuentos por país o subregión (selector) y por hora UTC. Todo sale del estado actual de la API. */
@Component({
  selector: 'app-recuentos',
  imports: [GraficoBarras, AvisoBloque],
  templateUrl: './recuentos.html',
  styleUrl: './recuentos.css',
})
export class Recuentos {
  private readonly datos = inject(PanelDatosService);
  private readonly store = inject(FiltrosStore);
  protected readonly i18n = inject(I18nService);

  protected readonly agrupacion = signal<Agrupacion>('pais');
  protected readonly bloquePais = this.datos.porPais;
  protected readonly bloqueSubregion = this.datos.porSubregion;
  protected readonly bloqueHora = this.datos.porHora;
  protected readonly horaAcotada = this.datos.horaAcotada;
  /** Sin fechas, `/recuentos/hora` usa su ventana de 24 h; el resto de bloques, todo el periodo. */
  protected readonly horaSinFechas = computed(() => {
    const f = this.store.aplicados();
    return !f.desde && !f.hasta;
  });
  protected readonly enReproduccion = computed(() => this.store.vista().modo === 'replay');

  protected readonly bloqueGrupo = computed(() =>
    this.agrupacion() === 'pais' ? this.bloquePais() : this.bloqueSubregion(),
  );

  /**
   * Todas las categorías (tabla equivalente). Los nombres del catálogo no se traducen; «Sin país asignado»,
   * que llega como una categoría más, sí.
   */
  protected readonly categorias = computed<DatoBarra[]>(() => {
    const d = this.bloqueGrupo().datos;
    if (!d) return [];
    const t = this.i18n.t();
    return d.categorias.map((c, i) => ({
      clave: `${this.agrupacion()}-${'codigo' in c ? (c.codigo ?? 'sin') : c.nombre}-${i}`,
      etiqueta: nombreVisible(c.nombre, t),
      valor: c.recuento,
    }));
  });
  protected readonly barrasGrupo = computed(() => {
    const t = this.i18n.t();
    return principalesConResto(
      this.categorias(),
      MAX_BARRAS,
      [nombreVisible(SIN_PAIS, t)],
      t('grafico.resto'),
    );
  });
  protected readonly hayResto = computed(() => this.categorias().length > MAX_BARRAS);

  protected readonly ventanas = computed<DatoBarra[]>(() => {
    const d = this.bloqueHora().datos;
    if (!d) return [];
    const t = this.i18n.t();
    return d.ventanas.map((v) => ({
      clave: v.inicio,
      etiqueta: etiquetaVentanaUtc(v.inicio, t),
      etiquetaCorta: etiquetaHoraUtc(v.inicio, t),
      valor: v.recuento,
    }));
  });
  protected readonly ceros = computed(() => this.ventanas().filter((v) => v.valor === 0).length);

  /** Categorías con país o subregión asignados («Sin país asignado» no cuenta como uno más). */
  protected readonly asignadas = computed(
    () => (this.bloqueGrupo().datos?.categorias ?? []).filter((c) => c.nombre !== SIN_PAIS).length,
  );
  /** Ventana con más eventos (la primera, si empatan); nulo si todas están a cero. */
  protected readonly pico = computed(() => {
    const d = this.bloqueHora().datos;
    if (!d) return null;
    const mayor = d.ventanas.reduce<(typeof d.ventanas)[number] | null>(
      (a, v) => (v.recuento > (a?.recuento ?? 0) ? v : a),
      null,
    );
    if (!mayor) return null;
    return {
      hora: etiquetaHoraUtc(mayor.inicio, this.i18n.t()),
      valor: this.i18n.entero(mayor.recuento),
    };
  });
  private readonly mediaHora = computed(() => {
    const v = this.ventanas();
    return v.length === 0 ? null : v.reduce((s, x) => s + (x.valor ?? 0), 0) / v.length;
  });
  protected readonly mediaHoraTexto = computed(() =>
    formatearDecimal(this.mediaHora(), 1, this.i18n.t()),
  );
  protected readonly referenciaHora = computed<Referencia | null>(() => {
    const m = this.mediaHora();
    return m === null || m <= 0
      ? null
      : {
          valor: m,
          etiqueta: this.i18n.tr('recuentos.media_ref', { valor: this.mediaHoraTexto() }),
        };
  });

  protected readonly agrupaciones = [
    { valor: 'pais', clave: 'filtros.pais' },
    { valor: 'subregion', clave: 'filtros.subregion' },
  ] as const;

  protected readonly rotuloGrupo = computed(() =>
    this.i18n.tr(
      this.agrupacion() === 'pais' ? 'recuentos.grupo_pais' : 'recuentos.grupo_subregion',
    ),
  );

  protected readonly maxBarras = MAX_BARRAS;

  protected cambiarAgrupacion(valor: string): void {
    this.agrupacion.set(valor === 'subregion' ? 'subregion' : 'pais');
  }
}
