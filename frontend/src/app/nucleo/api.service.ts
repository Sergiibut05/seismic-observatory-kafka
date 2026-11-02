import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, throwError } from 'rxjs';
import {
  ComparacionHistorica,
  Distribucion,
  EstadoApi,
  RecuentosHora,
  RecuentosPais,
  RecuentosSubregion,
  RespuestaEventos,
  RespuestaMapa,
} from '../modelos/api';
import { ConfigService } from './config.service';

/**
 * Cliente de la API 0.2.0. Solo `GET`: no hay otro método en la clase.
 * `query` es la cadena ya serializada por `aQuery()` (sin `?`).
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ConfigService);

  status(): Observable<EstadoApi> {
    return this.get('/status');
  }
  eventos(query = ''): Observable<RespuestaEventos> {
    return this.get('/eventos', query);
  }
  eventosMapa(query = ''): Observable<RespuestaMapa> {
    return this.get('/eventos/mapa', query);
  }
  recuentosPais(query = ''): Observable<RecuentosPais> {
    return this.get('/recuentos/pais', query);
  }
  recuentosSubregion(query = ''): Observable<RecuentosSubregion> {
    return this.get('/recuentos/subregion', query);
  }
  recuentosHora(query = ''): Observable<RecuentosHora> {
    return this.get('/recuentos/hora', query);
  }
  distribucionMagnitud(query = ''): Observable<Distribucion> {
    return this.get('/distribuciones/magnitud', query);
  }
  distribucionProfundidad(query = ''): Observable<Distribucion> {
    return this.get('/distribuciones/profundidad', query);
  }
  comparacionHistorica(query = ''): Observable<ComparacionHistorica> {
    return this.get('/comparacion-historica', query);
  }

  private get<T>(ruta: string, query = ''): Observable<T> {
    const base = this.config.apiBaseUrl();
    if (base === null) return throwError(() => ({ tipo: 'configuracion' }));
    return this.http.get<T>(`${base}${ruta}${query ? `?${query}` : ''}`).pipe(
      // Una página de aviso de ngrok llega como 200 con HTML: no es un objeto JSON del contrato.
      map((cuerpo) => {
        if (typeof cuerpo !== 'object' || cuerpo === null) throw { tipo: 'respuesta_invalida' };
        return cuerpo;
      }),
    );
  }
}
