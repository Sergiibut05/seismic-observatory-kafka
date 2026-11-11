import { Component, computed, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { Traductor } from '../../i18n/traducir';
import { Distribucion } from '../../modelos/api';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { DatoBarra } from '../../puro/barras';
import { INTERVALOS_PROFUNDIDAD } from '../../puro/escalas';
import { formatearPorcentaje } from '../../puro/formato';
import { AvisoBloque } from '../grafico-barras/aviso-bloque';
import { GraficoBarras } from '../grafico-barras/grafico-barras';

/** Barras de una distribución: los intervalos de la API (datos, no se traducen) y, aparte, «Sin valor». */
function aBarras(d: Distribucion, t: Traductor): DatoBarra[] {
  const barras: DatoBarra[] = d.intervalos.map((i, n) => ({
    clave: `i${n}`,
    etiqueta: `${i.etiqueta} ${d.unidad === 'km' ? 'km' : ''}`.trim(),
    etiquetaCorta: i.etiqueta,
    valor: i.recuento,
    // La profundidad lleva bajo el eje el color que ese intervalo tiene en el mapa.
    color:
      d.unidad === 'km'
        ? INTERVALOS_PROFUNDIDAD.find((p) => p.etiqueta === i.etiqueta)?.color
        : undefined,
  }));
  barras.push({
    clave: 'sin-valor',
    etiqueta: t('grafico.sin_valor'),
    valor: d.sin_valor,
    sinValor: true,
  });
  return barras;
}

/** Intervalo con más eventos y qué parte del total es (nulo si todos están a cero). */
function moda(d: Distribucion | null, t: Traductor): { etiqueta: string; cuota: string } | null {
  if (!d || d.total <= 0) return null;
  const mayor = d.intervalos.reduce<Distribucion['intervalos'][number] | null>(
    (a, i) => (i.recuento > (a?.recuento ?? 0) ? i : a),
    null,
  );
  if (!mayor) return null;
  return {
    etiqueta: `${mayor.etiqueta}${d.unidad === 'km' ? ' km' : ''}`,
    cuota: formatearPorcentaje((mayor.recuento / d.total) * 100, t),
  };
}

/** Distribuciones de magnitud y profundidad (con filtros activos). */
@Component({
  selector: 'app-distribuciones',
  imports: [GraficoBarras, AvisoBloque],
  templateUrl: './distribuciones.html',
  styleUrl: './distribuciones.css',
})
export class Distribuciones {
  private readonly datos = inject(PanelDatosService);
  protected readonly i18n = inject(I18nService);

  protected readonly bloqueMagnitud = this.datos.distMagnitud;
  protected readonly bloqueProfundidad = this.datos.distProfundidad;

  protected readonly barrasMagnitud = computed(() => {
    const d = this.bloqueMagnitud().datos;
    return d ? aBarras(d, this.i18n.t()) : [];
  });
  protected readonly barrasProfundidad = computed(() => {
    const d = this.bloqueProfundidad().datos;
    return d ? aBarras(d, this.i18n.t()) : [];
  });
  protected readonly modaMagnitud = computed(() =>
    moda(this.bloqueMagnitud().datos, this.i18n.t()),
  );
  protected readonly modaProfundidad = computed(() =>
    moda(this.bloqueProfundidad().datos, this.i18n.t()),
  );
}
