import { Component, computed, inject, input } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { Bloque, bloqueConDatosAntiguos } from '../../nucleo/panel-datos.service';
import { textoNd } from '../../puro/formato';

/**
 * Carga y error de un bloque (FR-011): «Cargando…» sin datos, error sin datos, o error con los
 * últimos datos correctos etiquetados como antiguos. No usa `role="alert"` (solo lo usa la barra de estado).
 */
@Component({
  selector: 'app-aviso-bloque',
  template: `
    @if (cargandoSinDatos()) {
      <p class="cargando">{{ i18n.tr('aviso.cargando') }}</p>
    } @else if (errorSinDatos()) {
      <p class="aviso aviso--atencion">
        {{ i18n.tr('aviso.error', { motivo: i18n.motivo(bloque().error) }) }}
      </p>
    } @else if (antiguos()) {
      <p class="aviso aviso--atencion">
        {{ i18n.tr('aviso.antiguos', { motivo: i18n.motivo(bloque().error), hora: ultimaLectura() }) }}
      </p>
    }
  `,
  styles: `
    :host {
      display: block;
    }
    :host:empty {
      display: none;
    }
    p {
      margin: 0 0 var(--e-3);
    }
  `,
})
export class AvisoBloque {
  protected readonly i18n = inject(I18nService);
  readonly bloque = input.required<Bloque<unknown>>();

  protected readonly cargandoSinDatos = computed(
    () => this.bloque().datos === null && this.bloque().error === null,
  );
  protected readonly errorSinDatos = computed(
    () => this.bloque().datos === null && this.bloque().error !== null,
  );
  protected readonly antiguos = computed(() => bloqueConDatosAntiguos(this.bloque()));
  protected readonly ultimaLectura = computed(() => {
    const t = this.bloque().lecturaOk;
    return t === null ? textoNd(this.i18n.t()) : this.i18n.horaConUtc(new Date(t).toISOString());
  });
}
