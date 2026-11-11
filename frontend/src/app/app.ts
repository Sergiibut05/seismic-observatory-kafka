import { Component, inject } from '@angular/core';
import { Comparacion } from './componentes/comparacion/comparacion';
import { Distribuciones } from './componentes/distribuciones/distribuciones';
import { Estado } from './componentes/estado/estado';
import { Filtros } from './componentes/filtros/filtros';
import { FraseFiltros } from './componentes/frase-filtros/frase-filtros';
import { Mapa } from './componentes/mapa/mapa';
import { NotaAviso } from './componentes/nota-aviso/nota-aviso';
import { Recuentos } from './componentes/recuentos/recuentos';
import { Superficies } from './componentes/superficies/superficies';
import { Tabla } from './componentes/tabla/tabla';
import { TemaService } from './nucleo/tema.service';
import { VistaDatos } from './componentes/vista-datos/vista-datos';
import { I18nService } from './i18n/i18n.service';
import { Idioma } from './i18n/traducir';
import { ConfigService } from './nucleo/config.service';
import { FiltrosStore } from './nucleo/filtros.store';
import { PanelUiStore } from './nucleo/panel-ui.store';
import { RefrescoService } from './nucleo/refresco.service';

/** Opciones del selector: los nombres de los idiomas se escriben en su propio idioma y no se traducen. */
const IDIOMAS: readonly { codigo: Idioma; rotulo: string; nombre: string }[] = [
  { codigo: 'es', rotulo: 'ES', nombre: 'Español' },
  { codigo: 'en', rotulo: 'EN', nombre: 'English' },
];

@Component({
  selector: 'app-root',
  imports: [
    Estado,
    VistaDatos,
    FraseFiltros,
    Superficies,
    Filtros,
    Mapa,
    Tabla,
    Recuentos,
    Distribuciones,
    Comparacion,
    NotaAviso,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly config = inject(ConfigService);
  protected readonly i18n = inject(I18nService);
  protected readonly idiomas = IDIOMAS;
  /** Solo para rotular la cabecera (que es fija) según la vista; los datos los pide `RefrescoService`. */
  protected readonly vista = inject(FiltrosStore).vista;
  protected readonly ui = inject(PanelUiStore);
  protected readonly tema = inject(TemaService);

  /** La tinta nace en el centro del botón pulsado (con teclado, también). */
  protected alternarTema(evento: MouseEvent): void {
    const r = (evento.currentTarget as HTMLElement).getBoundingClientRect();
    this.tema.alternar({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
  }

  constructor() {
    // Con la configuración inválida no se hace ninguna petición (FR-012).
    if (this.config.valida()) inject(RefrescoService).iniciar();
  }
}
