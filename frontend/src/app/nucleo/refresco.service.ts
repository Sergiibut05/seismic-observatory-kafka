import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal, untracked } from '@angular/core';
import { ColaRefresco } from '../puro/cola-refresco';
import { FiltrosAplicados, VistaDatos } from '../puro/filtros';
import { FiltrosStore } from './filtros.store';
import { PanelDatosService } from './panel-datos.service';

/**
 * Orquesta el refresco (FR-010): una ronda al arrancar y cada 60 s, una ronda por cambio
 * de filtros aplicados o de vista (en directo/REPRODUCCIÓN, sintéticos), pausa con la pestaña
 * oculta y ronda inmediata al volver. La paginación de la tabla solo recarga la tabla.
 */
@Injectable({ providedIn: 'root' })
export class RefrescoService {
  private readonly datos = inject(PanelDatosService);
  private readonly store = inject(FiltrosStore);
  private readonly documento = inject(DOCUMENT);

  private readonly activo = signal(false);
  private readonly cola = new ColaRefresco(() => this.datos.rondaCompleta());
  private anteriores: FiltrosAplicados | undefined;
  private vistaAnterior: VistaDatos | undefined;

  constructor() {
    effect(() => {
      if (!this.activo()) return;
      const aplicados = this.store.aplicados();
      const vista = this.store.vista();
      this.store.pagina();
      untracked(() => {
        const cambioVista = this.vistaAnterior !== undefined && vista !== this.vistaAnterior;
        this.vistaAnterior = vista;
        if (cambioVista) {
          // Otro conjunto de datos: los selectores de país y subregión también cambian.
          void this.datos.cargarOpciones();
        }
        if (aplicados !== this.anteriores || cambioVista) {
          this.anteriores = aplicados;
          this.cola.pedir();
        } else {
          void this.datos.cargarTabla();
        }
      });
    });
  }

  /** Arranca el refresco. Idempotente. Lo llama la app cuando la configuración es válida. */
  iniciar(): void {
    if (this.activo()) return;
    if (this.documento.visibilityState === 'hidden') this.cola.pausar();
    this.documento.addEventListener('visibilitychange', this.alCambiarVisibilidad);
    void this.datos.cargarOpciones();
    this.activo.set(true);
  }

  /** Pide una ronda ya (se coalesce con la que esté en curso). */
  refrescarAhora(): void {
    this.cola.pedir();
  }

  private readonly alCambiarVisibilidad = (): void => {
    if (this.documento.visibilityState === 'hidden') this.cola.pausar();
    else this.cola.reanudar();
  };
}
