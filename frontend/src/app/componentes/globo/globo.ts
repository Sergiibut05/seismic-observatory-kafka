import {
  Component,
  DestroyRef,
  ElementRef,
  InjectionToken,
  ViewEncapsulation,
  afterNextRender,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import type { GlobeInstance } from 'globe.gl';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { AnilloGlobo, PuntoGlobo, anillosGlobo, colorAnillo, etiquetaGlobo, puntosGlobo } from '../../puro/globo';

/** jsdom no tiene WebGL: allí el globo no se inicia. En un navegador es siempre `true`. */
export const GLOBO_HABILITADO = new InjectionToken<boolean>('GLOBO_HABILITADO', {
  providedIn: 'root',
  factory: () => typeof navigator === 'undefined' || !/jsdom/i.test(navigator.userAgent),
});

const URL_FRONTERAS = 'datos/paises.geojson';
const COLOR_OCEANO = '#10283d';
const COLOR_TIERRA = 'rgba(58, 84, 78, 0.95)';
const COLOR_FRONTERA = '#7d9a92';
const COLOR_FONDO = '#0d1b2a';
const COLOR_ATMOSFERA = '#8fbcd4';
const COLOR_SELECCION = '#ffd166';

/**
 * Globo 3D (feature 008): la misma respuesta de `/eventos/mapa` que el mapa plano, con pulsaciones en los
 * eventos más recientes. globe.gl se carga al abrir el globo, nunca en la carga inicial del panel.
 */
@Component({
  selector: 'app-globo',
  templateUrl: './globo.html',
  styleUrl: './globo.css',
  encapsulation: ViewEncapsulation.None, // la etiqueta flotante la crea globe.gl fuera de la plantilla
})
export class Globo {
  private readonly datos = inject(PanelDatosService);
  private readonly store = inject(FiltrosStore);
  private readonly habilitado = inject(GLOBO_HABILITADO);
  private readonly destroyRef = inject(DestroyRef);
  private readonly lienzo = viewChild<ElementRef<HTMLElement>>('lienzo');

  protected readonly estado = signal<'cargando' | 'listo' | 'sin-webgl' | 'inactivo'>(
    this.habilitado ? 'cargando' : 'inactivo',
  );
  protected readonly movimientoReducido =
    typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  private globo: GlobeInstance | null = null;
  private observador: ResizeObserver | null = null;
  private destruido = false;

  constructor() {
    afterNextRender(() => void this.iniciar());

    effect(() => {
      const respuesta = this.datos.mapa().datos;
      if (this.estado() !== 'listo') return;
      untracked(() => this.pintar(respuesta?.features ?? []));
    });

    effect(() => {
      const id = this.store.eventoSeleccionado();
      if (this.estado() !== 'listo') return;
      untracked(() => this.centrar(id));
    });

    this.destroyRef.onDestroy(() => {
      this.destruido = true;
      this.observador?.disconnect();
      this.globo?._destructor();
      this.globo = null;
    });
  }

  private async iniciar(): Promise<void> {
    const el = this.lienzo()?.nativeElement;
    if (!this.habilitado || !el) return;
    if (!soportaWebgl()) {
      this.estado.set('sin-webgl');
      return;
    }
    try {
      const { default: Globe } = await import('globe.gl');
      if (this.destruido) return;
      const globo = new Globe(el, { animateIn: !this.movimientoReducido })
        .backgroundColor(COLOR_FONDO)
        .showAtmosphere(true)
        .atmosphereColor(COLOR_ATMOSFERA)
        .atmosphereAltitude(0.18)
        .showGraticules(true)
        .pointLat('lat')
        .pointLng('lng')
        .pointAltitude('altura')
        .pointRadius('radio')
        .pointColor((p: object) => this.colorPunto(p as PuntoGlobo))
        .pointLabel((p: object) => etiquetaGlobo((p as PuntoGlobo).props))
        .pointsTransitionDuration(0)
        .onPointClick((p: object) => this.store.eventoSeleccionado.set((p as PuntoGlobo).id))
        .ringLat('lat')
        .ringLng('lng')
        .ringColor((a: object) => colorAnillo((a as AnilloGlobo).color))
        .ringMaxRadius('radioMax')
        .ringPropagationSpeed('velocidad')
        .ringRepeatPeriod('periodo')
        .ringAltitude(0.003)
        .polygonCapColor(() => COLOR_TIERRA)
        .polygonSideColor(() => 'rgba(0, 0, 0, 0)')
        .polygonStrokeColor(() => COLOR_FRONTERA)
        .polygonAltitude(0.004)
        .pointOfView({ lat: 20, lng: -40, altitude: 2.4 });

      const material = globo.globeMaterial() as unknown as { color?: { set(c: string): void } };
      material.color?.set(COLOR_OCEANO);

      const controles = globo.controls() as unknown as {
        autoRotate: boolean;
        autoRotateSpeed: number;
        addEventListener(tipo: string, fn: () => void): void;
      };
      controles.autoRotate = !this.movimientoReducido;
      controles.autoRotateSpeed = 0.35;
      controles.addEventListener('start', () => (controles.autoRotate = false));

      this.globo = globo;
      this.ajustarTamano(el);
      this.observador = new ResizeObserver(() => this.ajustarTamano(el));
      this.observador.observe(el);
      this.estado.set('listo');
      void this.cargarFronteras(globo);
    } catch (e) {
      console.error(`service=panel result=error bloque=globo motivo="no se pudo iniciar" detalle="${String(e)}"`);
      this.estado.set('sin-webgl');
    }
  }

  private async cargarFronteras(globo: GlobeInstance): Promise<void> {
    try {
      const r = await fetch(URL_FRONTERAS);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const geo = (await r.json()) as { features: object[] };
      if (this.globo === globo) globo.polygonsData(geo.features);
    } catch (e) {
      // El globo sigue sin fronteras: los eventos son lo importante.
      console.warn(`service=panel result=error bloque=globo-fronteras motivo="no se pudo cargar" detalle="${String(e)}"`);
    }
  }

  private pintar(features: Parameters<typeof puntosGlobo>[0]): void {
    if (!this.globo) return;
    this.globo
      .pointsData(puntosGlobo(features))
      .ringsData(anillosGlobo(features, { movimientoReducido: this.movimientoReducido }));
  }

  private colorPunto(p: PuntoGlobo): string {
    return p.id === this.store.eventoSeleccionado() ? COLOR_SELECCION : p.color;
  }

  private centrar(id: string | null): void {
    const globo = this.globo;
    if (!globo) return;
    // Repintar el color: el punto elegido pasa a amarillo y el anterior recupera el suyo.
    globo.pointColor((p: object) => this.colorPunto(p as PuntoGlobo));
    if (!id) return;
    const punto = (globo.pointsData() as PuntoGlobo[]).find((p) => p.id === id);
    if (!punto) return;
    (globo.controls() as unknown as { autoRotate: boolean }).autoRotate = false;
    globo.pointOfView({ lat: punto.lat, lng: punto.lng, altitude: 1.4 }, this.movimientoReducido ? 0 : 900);
  }

  private ajustarTamano(el: HTMLElement): void {
    if (!this.globo) return;
    this.globo.width(el.clientWidth).height(el.clientHeight);
  }
}

function soportaWebgl(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') ?? c.getContext('webgl'));
  } catch {
    return false;
  }
}
