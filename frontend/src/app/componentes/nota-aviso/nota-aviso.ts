import { Component, inject } from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';

/** Límite de las cifras: lo que USGS publica, sin predicción ni riesgo. */
@Component({
  selector: 'app-nota-aviso',
  templateUrl: './nota-aviso.html',
  styleUrl: './nota-aviso.css',
})
export class NotaAviso {
  protected readonly i18n = inject(I18nService);
}
