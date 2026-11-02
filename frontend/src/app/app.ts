import { Component, inject } from '@angular/core';
import { Comparacion } from './componentes/comparacion/comparacion';
import { Distribuciones } from './componentes/distribuciones/distribuciones';
import { Estado } from './componentes/estado/estado';
import { Filtros } from './componentes/filtros/filtros';
import { Mapa } from './componentes/mapa/mapa';
import { NotaAviso } from './componentes/nota-aviso/nota-aviso';
import { Recuentos } from './componentes/recuentos/recuentos';
import { Tabla } from './componentes/tabla/tabla';
import { ConfigService } from './nucleo/config.service';
import { RefrescoService } from './nucleo/refresco.service';

@Component({
  selector: 'app-root',
  imports: [Estado, Filtros, Mapa, Tabla, Recuentos, Distribuciones, Comparacion, NotaAviso],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly config = inject(ConfigService);

  constructor() {
    // Con la configuración inválida no se hace ninguna petición (FR-012).
    if (this.config.valida()) inject(RefrescoService).iniciar();
  }
}
