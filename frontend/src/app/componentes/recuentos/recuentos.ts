import { Component, computed, inject, signal } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { DatoBarra, etiquetaHoraUtc, etiquetaVentanaUtc, principalesConResto } from '../../puro/barras';
import { SIN_PAIS, nombreVisible } from '../../puro/filtros';
import { AvisoBloque } from '../grafico-barras/aviso-bloque';
import { GraficoBarras } from '../grafico-barras/grafico-barras';

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

  protected readonly rotuloGrupo = computed(() =>
    this.i18n.tr(this.agrupacion() === 'pais' ? 'recuentos.grupo_pais' : 'recuentos.grupo_subregion'),
  );

  protected readonly maxBarras = MAX_BARRAS;

  protected cambiarAgrupacion(valor: string): void {
    this.agrupacion.set(valor === 'subregion' ? 'subregion' : 'pais');
  }
}
