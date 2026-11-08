import { Component, computed, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { ModoDatos } from '../../puro/filtros';

/**
 * Origen de los datos (FR-013 y FR-020 de 007): selector «Datos» (en directo / REPRODUCCIÓN),
 * interruptor de casos sintéticos y las franjas que lo avisan. Solo escribe en `FiltrosStore`
 * y no persiste nada: al recargar, en directo y sin sintéticos.
 */
@Component({
  selector: 'app-vista-datos',
  templateUrl: './vista-datos.html',
  styleUrl: './vista-datos.css',
})
export class VistaDatos {
  private readonly store = inject(FiltrosStore);
  protected readonly i18n = inject(I18nService);

  protected readonly vista = this.store.vista;
  protected readonly esReplay = computed(() => this.vista().modo === 'replay');
  protected readonly sinteticos = computed(() => this.vista().sinteticos);

  protected elegirModo(modo: ModoDatos): void {
    this.store.fijarModo(modo);
  }

  protected alternarSinteticos(evento: Event): void {
    this.store.fijarSinteticos((evento.target as HTMLInputElement).checked);
  }
}
