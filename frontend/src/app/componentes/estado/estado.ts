import { Component, computed, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { Aviso, textoAviso } from '../../puro/desactualizado';
import { textoNd } from '../../puro/formato';

/** Barra de estado del sistema (FR-008): frescura de los datos y avisos destacados. */
@Component({
  selector: 'app-estado',
  templateUrl: './estado.html',
  styleUrl: './estado.css',
})
export class Estado {
  private readonly datos = inject(PanelDatosService);
  private readonly store = inject(FiltrosStore);
  protected readonly i18n = inject(I18nService);
  protected readonly bloque = this.datos.status;

  /** Último acceso correcto a la API, medido por el panel (no por la API). */
  protected readonly ultimoAcceso = computed(() => {
    const t = this.datos.ultimoAccesoOk();
    return t === null ? textoNd(this.i18n.t()) : this.i18n.horaConUtc(new Date(t).toISOString());
  });
  protected readonly ultimaIngesta = computed(() =>
    this.i18n.instante(this.bloque().datos?.ultima_ingesta_correcta),
  );
  protected readonly periodo = computed(() => {
    const p = this.bloque().datos?.periodo_consultado;
    return p
      ? `${this.i18n.instante(p.desde)} → ${this.i18n.instante(p.hasta)}`
      : textoNd(this.i18n.t());
  });
  protected readonly eventosReales = computed(() => this.i18n.entero(this.bloque().datos?.eventos_reales));
  protected readonly esReplay = computed(() => this.store.vista().modo === 'replay');
  /** Eventos de `replay.evento_actual`; «ND» si no hay base de datos (`null`). */
  protected readonly eventosReplay = computed(() => this.i18n.entero(this.bloque().datos?.eventos_replay));

  private readonly avisos = computed<Aviso[]>(() => this.datos.estadoSistema().avisos);
  /** El único `role="alert"`: el aviso más grave (API sin respuesta o base caída), si lo hay. */
  protected readonly alerta = computed<Aviso | null>(
    () =>
      this.avisos().find((a) => a.codigo === 'api_sin_respuesta') ??
      this.avisos().find((a) => a.codigo === 'base_fallida') ??
      null,
  );
  /** Resto de avisos, en la región `aria-live="polite"`. */
  protected readonly avisosCorteses = computed(() => this.avisos().filter((a) => a !== this.alerta()));
  protected readonly cargando = computed(
    () => this.bloque().datos === null && this.bloque().error === null,
  );

  /** El aviso se guarda con su código; el texto se arma con el idioma vigente. */
  protected textoAviso(a: Aviso): string {
    return textoAviso(a.codigo, this.i18n.t());
  }
}
