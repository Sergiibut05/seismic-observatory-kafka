import { Component, computed, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { PanelUiStore } from '../../nucleo/panel-ui.store';
import { TrozoFrase, trozosFrase } from '../../puro/frase-filtros';

/** Frase editable de filtros activos (010). Abre el formulario único, no uno nuevo. */
@Component({
  selector: 'app-frase-filtros',
  templateUrl: './frase-filtros.html',
  styleUrl: './frase-filtros.css',
})
export class FraseFiltros {
  private readonly store = inject(FiltrosStore);
  private readonly datos = inject(PanelDatosService);
  protected readonly ui = inject(PanelUiStore);
  protected readonly i18n = inject(I18nService);

  protected readonly trozos = computed<TrozoFrase[]>(() => {
    const pais = this.store.aplicados().pais;
    const nombre = this.datos
      .opcionesPais()
      .datos?.categorias.find((c) => c.codigo === pais)?.nombre;
    return trozosFrase(this.store.vista(), this.store.aplicados(), this.i18n.t(), nombre);
  });

  protected abrir(trozo: TrozoFrase): void {
    this.ui.abrirFiltro(trozo.campo);
  }
}
