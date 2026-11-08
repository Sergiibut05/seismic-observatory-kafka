import { Component, computed, inject, signal } from '@angular/core';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { DatoBarra, etiquetaHoraUtc, etiquetaVentanaUtc, principalesConResto } from '../../puro/barras';
import { formatearEntero, formatearInstanteUtc } from '../../puro/formato';
import { AvisoBloque } from '../grafico-barras/aviso-bloque';
import { GraficoBarras } from '../grafico-barras/grafico-barras';

export type Agrupacion = 'pais' | 'subregion';

const MAX_BARRAS = 15;
const SIN_PAIS = 'Sin país asignado';

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

  /** Todas las categorías (tabla equivalente); «Sin país asignado» llega como una más. */
  protected readonly categorias = computed<DatoBarra[]>(() => {
    const d = this.bloqueGrupo().datos;
    if (!d) return [];
    return d.categorias.map((c, i) => ({
      clave: `${this.agrupacion()}-${'codigo' in c ? (c.codigo ?? 'sin') : c.nombre}-${i}`,
      etiqueta: c.nombre,
      valor: c.recuento,
    }));
  });
  protected readonly barrasGrupo = computed(() =>
    principalesConResto(this.categorias(), MAX_BARRAS, [SIN_PAIS], 'Resto'),
  );
  protected readonly hayResto = computed(() => this.categorias().length > MAX_BARRAS);

  protected readonly ventanas = computed<DatoBarra[]>(() => {
    const d = this.bloqueHora().datos;
    if (!d) return [];
    return d.ventanas.map((v) => ({
      clave: v.inicio,
      etiqueta: etiquetaVentanaUtc(v.inicio),
      etiquetaCorta: etiquetaHoraUtc(v.inicio),
      valor: v.recuento,
    }));
  });
  protected readonly ceros = computed(() => this.ventanas().filter((v) => v.valor === 0).length);

  protected readonly rotuloGrupo = computed(() =>
    this.agrupacion() === 'pais' ? 'Eventos por país' : 'Eventos por subregión',
  );

  protected readonly maxBarras = MAX_BARRAS;
  protected readonly formatearEntero = formatearEntero;
  protected readonly formatearInstanteUtc = formatearInstanteUtc;

  protected cambiarAgrupacion(valor: string): void {
    this.agrupacion.set(valor === 'subregion' ? 'subregion' : 'pais');
  }
}
