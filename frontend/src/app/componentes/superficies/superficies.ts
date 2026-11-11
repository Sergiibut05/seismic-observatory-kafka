import { Component, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { PanelUiStore, SuperficiePanel } from '../../nucleo/panel-ui.store';

const OPCIONES: readonly { id: SuperficiePanel; clave: 'superficie.mapa' | 'superficie.tabla' | 'superficie.analisis' }[] =
  [
    { id: 'mapa', clave: 'superficie.mapa' },
    { id: 'tabla', clave: 'superficie.tabla' },
    { id: 'analisis', clave: 'superficie.analisis' },
  ];

/** Conmutador móvil: una superficie cada vez. El DOM de la rejilla no se reordena. */
@Component({
  selector: 'app-superficies',
  templateUrl: './superficies.html',
  styleUrl: './superficies.css',
})
export class Superficies {
  protected readonly ui = inject(PanelUiStore);
  protected readonly i18n = inject(I18nService);
  protected readonly opciones = OPCIONES;

  protected elegir(id: SuperficiePanel): void {
    this.ui.fijarSuperficie(id);
  }
}
