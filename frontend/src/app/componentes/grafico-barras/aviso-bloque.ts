import { Component, computed, input } from '@angular/core';
import { Bloque, bloqueConDatosAntiguos } from '../../nucleo/panel-datos.service';
import { formatearHoraConUtc } from '../../puro/formato';

/**
 * Carga y error de un bloque (FR-011): «Cargando…» sin datos, error sin datos, o error con los
 * últimos datos correctos etiquetados como antiguos. No usa `role="alert"` (solo lo usa la barra de estado).
 */
@Component({
  selector: 'app-aviso-bloque',
  template: `
    @if (cargandoSinDatos()) {
      <p class="cargando">Cargando datos…</p>
    } @else if (errorSinDatos()) {
      <p class="aviso aviso--atencion">No se pudieron cargar los datos: {{ bloque().error?.motivo }}</p>
    } @else if (antiguos()) {
      <p class="aviso aviso--atencion">
        Datos desactualizados: no se pudo actualizar ({{ bloque().error?.motivo }}). Se muestra la
        última lectura correcta, de las {{ ultimaLectura() }}.
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
    return t === null ? 'ND' : formatearHoraConUtc(new Date(t).toISOString());
  });
}
