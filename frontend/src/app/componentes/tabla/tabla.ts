import { Component, computed, inject } from '@angular/core';
import { EventoTabla } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService, bloqueConDatosAntiguos } from '../../nucleo/panel-datos.service';
import { etiquetaDatosAntiguos } from '../../puro/etiqueta-antiguos';
import {
  formatearEntero,
  formatearInstanteUtc,
  formatearMagnitud,
  formatearProfundidad,
} from '../../puro/formato';

/** Tabla paginada de eventos (FR-003). Es también la alternativa por teclado al mapa. */
@Component({
  selector: 'app-tabla',
  templateUrl: './tabla.html',
  styleUrl: './tabla.css',
})
export class Tabla {
  protected readonly store = inject(FiltrosStore);
  private readonly datos = inject(PanelDatosService);

  protected readonly bloque = this.datos.tabla;
  protected readonly respuesta = computed(() => this.bloque().datos);
  protected readonly eventos = computed(() => this.respuesta()?.eventos ?? []);
  protected readonly antiguos = computed(() => bloqueConDatosAntiguos(this.bloque()));
  protected readonly etiquetaAntiguos = computed(() =>
    etiquetaDatosAntiguos(this.bloque().lecturaOk),
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

  protected readonly formatearEntero = formatearEntero;
  protected readonly formatearInstanteUtc = formatearInstanteUtc;
  protected readonly formatearMagnitud = formatearMagnitud;
  protected readonly formatearProfundidad = formatearProfundidad;

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
