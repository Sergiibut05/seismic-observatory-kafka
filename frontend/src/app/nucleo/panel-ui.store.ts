import { Injectable, signal } from '@angular/core';
import { CampoFiltro } from '../puro/filtros';

export type SuperficiePanel = 'mapa' | 'tabla' | 'analisis';
export type CampoFoco = CampoFiltro | 'modo';

/**
 * Encuadre del panel (010): globo a sangre, superficie móvil y diálogo de filtros.
 * No toca los filtros aplicados ni pide datos.
 */
@Injectable({ providedIn: 'root' })
export class PanelUiStore {
  readonly enGlobo = signal(false);
  readonly superficie = signal<SuperficiePanel>('mapa');
  readonly filtrosAbiertos = signal(false);
  readonly campoFoco = signal<CampoFoco | null>(null);

  fijarGlobo(activo: boolean): void {
    this.enGlobo.set(activo);
    if (!activo) this.cerrarFiltros();
  }

  fijarSuperficie(s: SuperficiePanel): void {
    this.superficie.set(s);
  }

  abrirFiltro(campo: CampoFoco): void {
    this.campoFoco.set(campo);
    this.filtrosAbiertos.set(true);
  }

  cerrarFiltros(): void {
    this.filtrosAbiertos.set(false);
    this.campoFoco.set(null);
  }
}
