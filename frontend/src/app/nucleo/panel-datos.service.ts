import { Injectable, WritableSignal, computed, inject, signal } from '@angular/core';
import { Observable, Subscription, finalize } from 'rxjs';
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
import { calcularEstado } from '../puro/desactualizado';
import { ErrorPanel, clasificarError } from '../puro/errores';
import { FiltrosAplicados, acotarVentanaHora, aQuery } from '../puro/filtros';
import { ApiService } from './api.service';
import { FiltrosStore } from './filtros.store';
import { RELOJ } from './reloj';

export type EstadoBloque = 'cargando' | 'ok' | 'error';

/**
 * Estado de un bloque de datos (FR-011).
 *  - `datos`: la última respuesta 200, conservada aunque la siguiente falle.
 *  - `lecturaOk`: instante (ms epoch, medido por el panel) de ese 200.
 *  - `error`: motivo del último fallo; solo se borra con un nuevo 200.
 * Mientras `estado` es `cargando`, `datos` y `error` siguen siendo los anteriores.
 */
export interface Bloque<T> {
  estado: EstadoBloque;
  datos: T | null;
  lecturaOk: number | null;
  error: ErrorPanel | null;
}

const bloqueInicial = <T>(): Bloque<T> => ({
  estado: 'cargando',
  datos: null,
  lecturaOk: null,
  error: null,
});

/** `true` si hay error y se está mostrando la última lectura correcta («desactualizados»). */
export function bloqueConDatosAntiguos(b: Bloque<unknown>): boolean {
  return b.error !== null && b.datos !== null;
}

@Injectable({ providedIn: 'root' })
export class PanelDatosService {
  private readonly api = inject(ApiService);
  private readonly store = inject(FiltrosStore);
  private readonly reloj = inject(RELOJ);
  private readonly suscripciones = new Map<string, Subscription>();

  // Los 9 bloques de la ronda de refresco.
  readonly status = signal<Bloque<EstadoApi>>(bloqueInicial());
  readonly mapa = signal<Bloque<RespuestaMapa>>(bloqueInicial());
  readonly tabla = signal<Bloque<RespuestaEventos>>(bloqueInicial());
  readonly porPais = signal<Bloque<RecuentosPais>>(bloqueInicial());
  readonly porSubregion = signal<Bloque<RecuentosSubregion>>(bloqueInicial());
  readonly porHora = signal<Bloque<RecuentosHora>>(bloqueInicial());
  readonly distMagnitud = signal<Bloque<Distribucion>>(bloqueInicial());
  readonly distProfundidad = signal<Bloque<Distribucion>>(bloqueInicial());
  readonly comparacion = signal<Bloque<ComparacionHistorica>>(bloqueInicial());

  // Opciones de los selectores: sin filtros, solo al arrancar (fuera de la ronda de 60 s).
  readonly opcionesPais = signal<Bloque<RecuentosPais>>(bloqueInicial());
  readonly opcionesSubregion = signal<Bloque<RecuentosSubregion>>(bloqueInicial());

  /** Ventana efectiva de `/recuentos/hora` cuando se acotó a 31 días; si no, `null`. */
  readonly horaAcotada = signal<{ desde: string; hasta: string } | null>(null);

  /** Última respuesta correcta de `/status` medida por el panel (ms epoch), o `null`. */
  readonly ultimoAccesoOk = computed(() => this.status().lecturaOk);
  /** Avisos destacados: API sin respuesta, base fallida, datos desactualizados. */
  readonly estadoSistema = computed(() =>
    calcularEstado(this.status().datos, this.status().error !== null),
  );

  /** Una ronda: `/status` + 8 bloques de datos (9 GET). Resuelve cuando todos terminan. */
  rondaCompleta(): Promise<void> {
    const f = this.store.aplicados();
    return Promise.all([
      this.cargar('status', this.status, () => this.api.status()),
      this.cargar('mapa', this.mapa, () => this.api.eventosMapa(aQuery(f, 'completo'))),
      this.cargarTabla(),
      this.cargar('porPais', this.porPais, () => this.api.recuentosPais(aQuery(f, 'completo'))),
      this.cargar('porSubregion', this.porSubregion, () =>
        this.api.recuentosSubregion(aQuery(f, 'completo')),
      ),
      this.cargarHora(f),
      this.cargar('distMagnitud', this.distMagnitud, () =>
        this.api.distribucionMagnitud(aQuery(f, 'completo')),
      ),
      this.cargar('distProfundidad', this.distProfundidad, () =>
        this.api.distribucionProfundidad(aQuery(f, 'completo')),
      ),
      this.cargar('comparacion', this.comparacion, () =>
        this.api.comparacionHistorica(aQuery(f, 'comparacion')),
      ),
    ]).then(() => undefined);
  }

  /** Solo la tabla (cambio de página). Cancela una petición de tabla anterior en vuelo. */
  cargarTabla(): Promise<void> {
    const f = this.store.aplicados();
    const { limite, desplazamiento } = this.store.pagina();
    return this.cargar('tabla', this.tabla, () =>
      this.api.eventos(aQuery(f, 'completo', { limite, desplazamiento })),
    );
  }

  /** Opciones de país y subregión sin filtros (2 GET, una sola vez al arrancar). */
  cargarOpciones(): Promise<void> {
    return Promise.all([
      this.cargar('opcionesPais', this.opcionesPais, () => this.api.recuentosPais('')),
      this.cargar('opcionesSubregion', this.opcionesSubregion, () => this.api.recuentosSubregion('')),
    ]).then(() => undefined);
  }

  private cargarHora(f: FiltrosAplicados): Promise<void> {
    const ahora = this.reloj();
    const acotada = acotarVentanaHora(f, ahora);
    this.horaAcotada.set(
      acotada.acotado ? { desde: acotada.filtros.desde ?? '', hasta: acotada.filtros.hasta ?? '' } : null,
    );
    return this.cargar('porHora', this.porHora, () =>
      this.api.recuentosHora(aQuery(f, 'hora', {}, ahora)),
    );
  }

  /**
   * Pide un bloque. Una petición nueva del mismo bloque cancela la anterior en vuelo
   * (nunca hay dos del mismo bloque a la vez). Nunca rechaza: el fallo queda en el bloque.
   */
  private cargar<T>(
    nombre: string,
    destino: WritableSignal<Bloque<T>>,
    peticion: () => Observable<T>,
  ): Promise<void> {
    return new Promise<void>((resolver) => {
      this.suscripciones.get(nombre)?.unsubscribe();
      destino.update((b) => ({ ...b, estado: 'cargando' }));
      const s = peticion()
        .pipe(finalize(() => resolver()))
        .subscribe({
          next: (datos) =>
            destino.set({ estado: 'ok', datos, lecturaOk: this.reloj(), error: null }),
          error: (e: unknown) => {
            const error = clasificarError(e);
            destino.update((b) => ({ ...b, estado: 'error', error }));
            console.warn(
              `service=panel result=error bloque=${nombre} tipo=${error.tipo} motivo="${error.motivo}"`,
            );
          },
        });
      this.suscripciones.set(nombre, s);
    });
  }
}
