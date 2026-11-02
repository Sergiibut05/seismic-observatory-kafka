import { Component, computed, inject } from '@angular/core';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { Aviso } from '../../puro/desactualizado';
import { formatearEntero, formatearHoraConUtc, formatearInstanteUtc, ND } from '../../puro/formato';

/** Barra de estado del sistema (FR-008): frescura de los datos y avisos destacados. */
@Component({
  selector: 'app-estado',
  templateUrl: './estado.html',
  styleUrl: './estado.css',
})
export class Estado {
  private readonly datos = inject(PanelDatosService);
  protected readonly bloque = this.datos.status;

  /** Último acceso correcto a la API, medido por el panel (no por la API). */
  protected readonly ultimoAcceso = computed(() => {
    const t = this.datos.ultimoAccesoOk();
    return t === null ? ND : formatearHoraConUtc(new Date(t).toISOString());
  });
  protected readonly ultimaIngesta = computed(() =>
    formatearInstanteUtc(this.bloque().datos?.ultima_ingesta_correcta),
  );
  protected readonly periodo = computed(() => {
    const p = this.bloque().datos?.periodo_consultado;
    return p ? `${formatearInstanteUtc(p.desde)} → ${formatearInstanteUtc(p.hasta)}` : ND;
  });
  protected readonly eventosReales = computed(() => formatearEntero(this.bloque().datos?.eventos_reales));

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
}
