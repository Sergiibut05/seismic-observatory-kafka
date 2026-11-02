import { HttpInterceptorFn } from '@angular/common/http';
import { throwError } from 'rxjs';

export const CABECERA_NGROK = 'ngrok-skip-browser-warning';

/**
 * Añade la cabecera que evita la página de aviso de ngrok y rechaza cualquier método que
 * no sea GET: el panel es de solo lectura y así se garantiza en un único sitio (AC-8).
 */
export const cabecerasInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.method !== 'GET') {
    return throwError(() => ({ tipo: 'metodo_no_permitido', metodo: req.method }));
  }
  return next(req.clone({ setHeaders: { [CABECERA_NGROK]: '1' } }));
};
