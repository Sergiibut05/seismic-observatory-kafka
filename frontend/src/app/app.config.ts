import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { cabecerasInterceptor } from './nucleo/cabeceras.interceptor';
import { ConfigService } from './nucleo/config.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([cabecerasInterceptor])),
    // Lee config.json antes de pintar nada; si falla, la app muestra el error de configuración.
    provideAppInitializer(() => inject(ConfigService).cargar()),
  ],
};
