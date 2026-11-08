import { Component, computed, inject } from '@angular/core';
import { EventoTabla } from '../../modelos/api';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService, bloqueConDatosAntiguos } from '../../nucleo/panel-datos.service';
import { etiquetaDatosAntiguos } from '../../puro/etiqueta-antiguos';
import { SIN_PAIS, nombreVisible } from '../../puro/filtros';

/** Tabla paginada de eventos (FR-003). Es también la alternativa por teclado al mapa. */
@Component({
  selector: 'app-tabla',
  templateUrl: './tabla.html',
  styleUrl: './tabla.css',
})
export class Tabla {
  protected readonly store = inject(FiltrosStore);
  protected readonly i18n = inject(I18nService);
  private readonly datos = inject(PanelDatosService);

  protected readonly bloque = this.datos.tabla;
  protected readonly respuesta = computed(() => this.bloque().datos);
  protected readonly eventos = computed(() => this.respuesta()?.eventos ?? []);
  /** La columna de reproducción sale de lo que dice la respuesta, no de lo que se acaba de elegir. */
  protected readonly esReplay = computed(() => this.respuesta()?.modo === 'replay');
  protected readonly antiguos = computed(() => bloqueConDatosAntiguos(this.bloque()));
  protected readonly etiquetaAntiguos = computed(() =>
    etiquetaDatosAntiguos(this.bloque().lecturaOk, undefined, this.i18n.t()),
  );

  protected readonly resumen = computed(() => {
    const r = this.respuesta();
    if (!r) return null;
    const total = r.total;
    const limite = Math.max(1, r.limite);
    const primero = total === 0 ? 0 : r.desplazamiento + 1;
    const ultimo = Math.min(total, r.desplazamiento + r.eventos.length);
    return {
      total,
      primero,
      ultimo,
      pagina: Math.floor(r.desplazamiento / limite) + 1,
      paginas: Math.max(1, Math.ceil(total / limite)),
      hayAnterior: r.desplazamiento > 0,
      haySiguiente: r.desplazamiento + limite < total,
      limite,
    };
  });

  protected readonly sinPais = SIN_PAIS;

  /** País o subregión tal como vienen del catálogo; solo la etiqueta fija «Sin país asignado» se traduce. */
  protected nombre(valor: string | null | undefined): string {
    return nombreVisible(valor, this.i18n.t());
  }

  protected seleccionado(e: EventoTabla): boolean {
    return this.store.eventoSeleccionado() === e.event_id;
  }

  protected seleccionar(e: EventoTabla): void {
    this.store.eventoSeleccionado.set(e.event_id);
  }

  protected anterior(): void {
    const r = this.resumen();
    if (r?.hayAnterior) this.store.irAPagina(this.store.pagina().desplazamiento - r.limite);
  }

  protected siguiente(): void {
    const r = this.resumen();
    if (r?.haySiguiente) this.store.irAPagina(this.store.pagina().desplazamiento + r.limite);
  }
}
