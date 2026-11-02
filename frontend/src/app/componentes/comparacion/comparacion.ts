import { Component, computed, inject } from '@angular/core';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { formatearInstanteUtc } from '../../puro/formato';
import {
  AVISO_PERIODO_INCOMPLETO,
  cifrasComparacion,
  describirFiltrosEfectivos,
} from '../../puro/texto-comparacion';
import { AvisoBloque } from '../grafico-barras/aviso-bloque';

/** Últimas 24 h frente a la media diaria de 2025 (el histórico puede no estar cargado). */
@Component({
  selector: 'app-comparacion',
  imports: [AvisoBloque],
  templateUrl: './comparacion.html',
  styleUrl: './comparacion.css',
})
export class Comparacion {
  protected readonly bloque = inject(PanelDatosService).comparacion;

  protected readonly datos = computed(() => this.bloque().datos);
  protected readonly cifras = computed(() => {
    const d = this.datos();
    return d ? cifrasComparacion(d) : null;
  });
  protected readonly filtros = computed(() => {
    const d = this.datos();
    return d ? describirFiltrosEfectivos(d.filtros_efectivos) : null;
  });
  /** El aviso de periodo incompleto se ve siempre: el de la API o, sin respuesta, el de respaldo. */
  protected readonly aviso = computed(() => this.datos()?.aviso || AVISO_PERIODO_INCOMPLETO);

  protected readonly formatearInstanteUtc = formatearInstanteUtc;
}
