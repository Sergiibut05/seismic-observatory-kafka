import { Component, computed, inject } from '@angular/core';
import { Distribucion } from '../../modelos/api';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { DatoBarra } from '../../puro/barras';
import { formatearEntero } from '../../puro/formato';
import { AvisoBloque } from '../grafico-barras/aviso-bloque';
import { GraficoBarras } from '../grafico-barras/grafico-barras';

/** Barras de una distribución: los intervalos de la API y, aparte, la categoría «Sin valor». */
function aBarras(d: Distribucion): DatoBarra[] {
  const barras: DatoBarra[] = d.intervalos.map((i, n) => ({
    clave: `i${n}`,
    etiqueta: `${i.etiqueta} ${d.unidad === 'km' ? 'km' : ''}`.trim(),
    etiquetaCorta: i.etiqueta,
    valor: i.recuento,
  }));
  barras.push({ clave: 'sin-valor', etiqueta: 'Sin valor', valor: d.sin_valor, sinValor: true });
  return barras;
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

  protected readonly bloqueMagnitud = this.datos.distMagnitud;
  protected readonly bloqueProfundidad = this.datos.distProfundidad;

  protected readonly barrasMagnitud = computed(() => {
    const d = this.bloqueMagnitud().datos;
    return d ? aBarras(d) : [];
  });
  protected readonly barrasProfundidad = computed(() => {
    const d = this.bloqueProfundidad().datos;
    return d ? aBarras(d) : [];
  });

  protected readonly formatearEntero = formatearEntero;
}
