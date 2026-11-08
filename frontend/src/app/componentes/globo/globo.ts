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

/** Versión simplificada solo para dibujar (`npm run fronteras:globo`); el país sigue saliendo del catálogo completo. */
const URL_FRONTERAS = 'datos/paises-globo.geojson';
const PIXEL_RATIO_MAX = 1.5;
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
  private visibilidad: IntersectionObserver | null = null;
  private enPantalla = true;
  private urlTextura: string | null = null;
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
      this.visibilidad?.disconnect();
      document.removeEventListener('visibilitychange', this.alCambiarPestana);
      this.globo?._destructor();
      this.globo = null;
      if (this.urlTextura) URL.revokeObjectURL(this.urlTextura);
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
        .pointResolution(6)
        .onPointClick((p: object) => this.store.eventoSeleccionado.set((p as PuntoGlobo).id))
        .ringLat('lat')
        .ringLng('lng')
        .ringColor((a: object) => colorAnillo((a as AnilloGlobo).color))
        .ringMaxRadius('radioMax')
        .ringPropagationSpeed('velocidad')
        .ringRepeatPeriod('periodo')
        .ringAltitude(0.003)
        .ringResolution(32)
        .pointOfView({ lat: 20, lng: -40, altitude: 2.4 });

      globo.renderer().setPixelRatio(Math.min(devicePixelRatio || 1, PIXEL_RATIO_MAX));

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
      // Sin esto globe.gl dibuja 60 fotogramas por segundo aunque el globo esté fuera de la vista.
      this.visibilidad = new IntersectionObserver(([e]) => {
        this.enPantalla = e.isIntersecting;
        this.actualizarAnimacion();
      });
      this.visibilidad.observe(el);
      document.addEventListener('visibilitychange', this.alCambiarPestana);
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
      const geo = (await r.json()) as { features: FronteraGeo[] };
      const url = await texturaTierra(geo.features);
      if (this.globo !== globo) {
        URL.revokeObjectURL(url);
        return;
      }
      this.urlTextura = url;
      globo.globeImageUrl(url);
      (globo.globeMaterial() as unknown as { color?: { set(c: string): void } }).color?.set('#ffffff');
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

  private readonly alCambiarPestana = (): void => this.actualizarAnimacion();

  private actualizarAnimacion(): void {
    if (!this.globo) return;
    if (this.enPantalla && document.visibilityState === 'visible') this.globo.resumeAnimation();
    else this.globo.pauseAnimation();
  }

  private ajustarTamano(el: HTMLElement): void {
    if (!this.globo) return;
    this.globo.width(el.clientWidth).height(el.clientHeight);
  }
}

interface FronteraGeo {
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] } | null;
}

const ANCHO_TEXTURA = 4096;

/**
 * Tierra y fronteras pintadas una vez en una textura equirectangular. Como polígonos 3D eran ~3600 llamadas de
 * dibujo por fotograma (21 fps); como textura es una sola.
 */
async function texturaTierra(features: readonly FronteraGeo[]): Promise<string> {
  const lienzo = document.createElement('canvas');
  lienzo.width = ANCHO_TEXTURA;
  lienzo.height = ANCHO_TEXTURA / 2;
  const ctx = lienzo.getContext('2d');
  if (!ctx) throw new Error('sin contexto 2d');
  const escala = ANCHO_TEXTURA / 360;
  ctx.fillStyle = COLOR_OCEANO;
  ctx.fillRect(0, 0, lienzo.width, lienzo.height);

  const tierra = new Path2D();
  for (const f of features) {
    if (!f.geometry) continue;
    const poligonos = (
      f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates
    ) as number[][][][];
    for (const anillos of poligonos) {
      for (const anillo of anillos) {
        anillo.forEach(([lng, lat], k) => {
          const x = (lng + 180) * escala;
          const y = (90 - lat) * escala;
          if (k === 0) tierra.moveTo(x, y);
          else tierra.lineTo(x, y);
        });
        tierra.closePath();
      }
    }
  }
  ctx.fillStyle = COLOR_TIERRA;
  ctx.fill(tierra, 'evenodd');
  ctx.strokeStyle = COLOR_FRONTERA;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.stroke(tierra);

  const blob = await new Promise<Blob | null>((ok) => lienzo.toBlob(ok, 'image/png'));
  if (!blob) throw new Error('no se pudo codificar la textura');
  return URL.createObjectURL(blob);
}

function soportaWebgl(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') ?? c.getContext('webgl'));
  } catch {
    return false;
  }
}
