import { Component, computed, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
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
  private readonly store = inject(FiltrosStore);
  protected readonly i18n = inject(I18nService);
  protected readonly bloque = inject(PanelDatosService).comparacion;
  /** En REPRODUCCIÓN no se pide la comparación: solo existe con datos en directo. */
  protected readonly esReplay = computed(() => this.store.vista().modo === 'replay');

  protected readonly datos = computed(() => this.bloque().datos);
  protected readonly cifras = computed(() => {
    const d = this.datos();
    return d ? cifrasComparacion(d, this.i18n.t()) : null;
  });
  protected readonly filtros = computed(() => {
    const d = this.datos();
    return d ? describirFiltrosEfectivos(d.filtros_efectivos, this.i18n.t()) : null;
  });
  /**
   * El aviso de periodo incompleto se ve siempre. En español, el de la API o, sin respuesta, el de
   * respaldo; en inglés, el del propio panel (el de la API es un texto fijo en español).
   */
  protected readonly aviso = computed(() =>
    this.i18n.idioma() === 'es'
      ? this.datos()?.aviso || AVISO_PERIODO_INCOMPLETO
      : this.i18n.tr('comparacion.aviso'),
  );
}
