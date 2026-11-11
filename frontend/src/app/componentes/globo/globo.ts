import {
  Component,
  DestroyRef,
  ElementRef,
  InjectionToken,
  ViewEncapsulation,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import type { GlobeInstance } from 'globe.gl';
import { I18nService } from '../../i18n/i18n.service';
import { Clave } from '../../i18n/es';
import { EventoMapa } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService } from '../../nucleo/panel-datos.service';
import { INTERVALOS_PROFUNDIDAD, radioPorMagnitud } from '../../puro/escalas';
import { formatearInstanteUtc, formatearMagnitud } from '../../puro/formato';
import {
  AnilloGlobo,
  PaisGlobo,
  PuntoGlobo,
  SerieEscena,
  anillosGlobo,
  barrasEscena,
  colorAnillo,
  etiquetaGlobo,
  instanteCinta,
  marcasCinta,
  paisEnPunto,
  puntosGlobo,
  recortarPorHora,
} from '../../puro/globo';
import { cifrasComparacion } from '../../puro/texto-comparacion';
import { GraficoBarras } from '../grafico-barras/grafico-barras';
import type { CapaColumnas } from './mallas';

export const GLOBO_HABILITADO = new InjectionToken<boolean>('GLOBO_HABILITADO', {
  providedIn: 'root',
  factory: () => typeof navigator === 'undefined' || !/jsdom/i.test(navigator.userAgent),
});

const URL_FRONTERAS = 'datos/paises-globo.geojson';
const PIXEL_RATIO_MAX = 1.5;
const COLOR_OCEANO = '#10283d';
const COLOR_TIERRA = 'rgba(58, 84, 78, 0.95)';
const COLOR_FRONTERA = '#7d9a92';
const COLOR_FONDO = '#070B12';
const COLOR_ATMOSFERA = '#8B7CFF';
const SERIES: readonly { id: SerieEscena; clave: Clave; titulo: Clave }[] = [
  { id: 'hora', clave: 'escena.serie_hora', titulo: 'recuentos.hora_titulo' },
  { id: 'magnitud', clave: 'escena.serie_magnitud', titulo: 'distribuciones.grafico_magnitud' },
  { id: 'profundidad', clave: 'escena.serie_profundidad', titulo: 'distribuciones.grafico_profundidad' },
];

@Component({
  selector: 'app-globo',
  imports: [GraficoBarras],
  templateUrl: './globo.html',
  styleUrl: './globo.css',
  encapsulation: ViewEncapsulation.None,
})
export class Globo {
  private readonly datos = inject(PanelDatosService);
  private readonly store = inject(FiltrosStore);
  protected readonly i18n = inject(I18nService);
  private readonly habilitado = inject(GLOBO_HABILITADO);
  private readonly destroyRef = inject(DestroyRef);
  private readonly lienzo = viewChild<ElementRef<HTMLElement>>('lienzo');

  protected readonly estado = signal<'cargando' | 'listo' | 'sin-webgl' | 'inactivo'>(
    this.habilitado ? 'cargando' : 'inactivo',
  );
  protected readonly movimientoReducido =
    typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  protected readonly graficaAbierta =
    typeof matchMedia !== 'function' || !matchMedia('(max-width: 40rem)').matches;
  protected readonly serie = signal<SerieEscena>('hora');
  protected readonly posCinta = signal(1000);
  protected readonly series = SERIES;
  protected readonly intervalos = INTERVALOS_PROFUNDIDAD;
  protected readonly radiosLeyenda = [
    { etiqueta: 'M 2', radio: radioPorMagnitud(2) },
    { etiqueta: 'M 5', radio: radioPorMagnitud(5) },
    { etiqueta: 'M 7', radio: radioPorMagnitud(7) },
  ];

  protected readonly esReplay = computed(() => this.store.vista().modo === 'replay');
  protected readonly cifras = computed(() => {
    const d = this.datos.comparacion().datos;
    return d ? cifrasComparacion(d, this.i18n.t()) : null;
  });

  private readonly crudos = computed(() => this.datos.mapa().datos?.features ?? []);
  private readonly corte = computed(() =>
    instanteCinta(this.posCinta() / 1000, Date.now(), this.crudos()),
  );
  protected readonly visibles = computed(() => recortarPorHora(this.crudos(), this.corte()));
  protected readonly marcas = computed(() => marcasCinta(this.crudos(), Date.now()));
  protected readonly etiquetaCorte = computed(() => formatearInstanteUtc(this.corte(), this.i18n.t()));
  protected readonly barras = computed(() =>
    barrasEscena(this.visibles(), this.serie(), Date.parse(this.corte()), this.i18n.t()),
  );
  protected readonly tituloSerie = computed(
    () => SERIES.find((s) => s.id === this.serie())?.titulo ?? 'escena.grafica',
  );

  private globo: GlobeInstance | null = null;
  private capa: CapaColumnas | null = null;
  private mallas: typeof import('./mallas') | null = null;
  private paises: PaisGlobo[] = [];
  private observador: ResizeObserver | null = null;
  private visibilidad: IntersectionObserver | null = null;
  private enPantalla = true;
  private urlTextura: string | null = null;
  private destruido = false;

  constructor() {
    afterNextRender(() => void this.iniciar());

    effect(() => {
      const visibles = this.visibles();
      if (this.estado() !== 'listo') return;
      untracked(() => this.pintar(visibles));
    });

    effect(() => {
      const id = this.store.eventoSeleccionado();
      if (this.estado() !== 'listo') return;
      untracked(() => this.centrar(id));
    });

    effect(() => {
      this.i18n.idioma();
      if (this.estado() !== 'listo') return;
      untracked(() => this.globo?.pointLabel((p: object) => this.etiquetaPunto(p as PuntoGlobo)));
    });

    this.destroyRef.onDestroy(() => {
      this.destruido = true;
      this.observador?.disconnect();
      this.visibilidad?.disconnect();
      document.removeEventListener('visibilitychange', this.alCambiarPestana);
      if (this.capa && this.globo && this.mallas) this.mallas.destruirCapa(this.capa, this.globo);
      this.globo?._destructor();
      this.globo = null;
      this.capa = null;
      if (this.urlTextura) URL.revokeObjectURL(this.urlTextura);
    });
  }

  protected moverCinta(evento: Event): void {
    const v = Number((evento.target as HTMLInputElement).value);
    this.posCinta.set(Number.isFinite(v) ? v : 1000);
  }

  private async iniciar(): Promise<void> {
    const el = this.lienzo()?.nativeElement;
    if (!this.habilitado || !el) return;
    if (!soportaWebgl()) {
      this.estado.set('sin-webgl');
      return;
    }
    try {
      const [{ default: Globe }, mallas] = await Promise.all([import('globe.gl'), import('./mallas')]);
      if (this.destruido) return;
      this.mallas = mallas;
      const globo = new Globe(el, { animateIn: !this.movimientoReducido })
        .backgroundColor(COLOR_FONDO)
        .showAtmosphere(true)
        .atmosphereColor(COLOR_ATMOSFERA)
        .atmosphereAltitude(0.18)
        .showGraticules(true)
        .pointLat('lat')
        .pointLng('lng')
        .pointAltitude((p: object) => (p as PuntoGlobo).altura)
        .pointRadius(0.04)
        .pointColor((p: object) => (p as PuntoGlobo).color)
        .pointLabel((p: object) => this.etiquetaPunto(p as PuntoGlobo))
        .pointsTransitionDuration(0)
        .pointResolution(8)
        .onPointClick((p: object) => this.store.eventoSeleccionado.set((p as PuntoGlobo).id))
        .ringLat('lat')
        .ringLng('lng')
        .ringColor((a: object) => colorAnillo((a as AnilloGlobo).color))
        .ringMaxRadius('radioMax')
        .ringPropagationSpeed('velocidad')
        .ringRepeatPeriod('periodo')
        .ringAltitude(0.003)
        .ringResolution(32)
        .polygonCapColor(() => 'rgba(91, 77, 255, 0.32)')
        .polygonSideColor(() => 'rgba(139, 124, 255, 0.12)')
        .polygonStrokeColor(() => '#F2F0FF')
        .polygonAltitude(0.006)
        .polygonsTransitionDuration(0)
        .htmlLat('lat')
        .htmlLng('lng')
        .htmlAltitude('alt')
        .htmlElement((d: object) => this.nodoMagnitud(d as { texto: string }))
        .htmlTransitionDuration(0)
        .onGlobeClick((c: { lat: number; lng: number }, ev: MouseEvent) => this.alClicGlobo(c, ev))
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
      this.capa = mallas.crearCapaColumnas(globo);
      this.ajustarTamano(el);
      this.observador = new ResizeObserver(() => this.ajustarTamano(el));
      this.observador.observe(el);
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
      const geo = (await r.json()) as { features: PaisGlobo[] };
      this.paises = geo.features;
      const url = await texturaTierra(geo.features);
      if (this.globo !== globo) {
        URL.revokeObjectURL(url);
        return;
      }
      this.urlTextura = url;
      globo.globeImageUrl(url);
      (globo.globeMaterial() as unknown as { color?: { set(c: string): void } }).color?.set('#ffffff');
    } catch (e) {
      console.warn(`service=panel result=error bloque=globo-fronteras motivo="no se pudo cargar" detalle="${String(e)}"`);
    }
  }

  private pintar(features: readonly EventoMapa[]): void {
    if (!this.globo) return;
    const puntos = puntosGlobo(features);
    this.globo
      .pointsData(puntos)
      .ringsData(anillosGlobo(features, { movimientoReducido: this.movimientoReducido }));
    if (this.capa && this.mallas) {
      this.mallas.actualizarColumnas(this.capa, this.globo, puntos, this.store.eventoSeleccionado());
    }
    this.pintarMagnitud(puntos);
  }

  private pintarMagnitud(puntos: PuntoGlobo[]): void {
    if (!this.globo) return;
    const id = this.store.eventoSeleccionado();
    const p = id ? puntos.find((x) => x.id === id) : undefined;
    this.globo.htmlElementsData(
      p
        ? [{ lat: p.lat, lng: p.lng, alt: p.altura + 0.02, texto: formatearMagnitud(p.props.magnitud, this.i18n.t()) }]
        : [],
    );
  }

  private nodoMagnitud(d: { texto: string }): HTMLElement {
    const el = document.createElement('div');
    el.className = 'globo-magnitud';
    el.textContent = d.texto;
    return el;
  }

  private alClicGlobo(coords: { lat: number; lng: number }, ev: MouseEvent): void {
    if (this.capa && this.globo && this.mallas) {
      const col = this.mallas.recogerColumna(this.capa, this.globo, ev);
      if (col) {
        this.store.eventoSeleccionado.set(col.id);
        return;
      }
    }
    const pais = paisEnPunto(this.paises, coords.lat, coords.lng);
    this.globo?.polygonsData(pais ? [pais] : []);
    const codigo = pais?.properties.ADM0_A3;
    if (!codigo) return;
    const opciones = this.datos.opcionesPais().datos?.categorias ?? [];
    if (!opciones.some((c) => c.codigo === codigo)) return;
    this.store.editar({ pais: codigo });
    this.store.aplicarYa();
  }

  private etiquetaPunto(p: PuntoGlobo): string {
    return etiquetaGlobo(p.props, this.i18n.t());
  }

  private centrar(id: string | null): void {
    const globo = this.globo;
    if (!globo) return;
    const puntos = globo.pointsData() as PuntoGlobo[];
    if (this.capa && this.mallas) this.mallas.actualizarColumnas(this.capa, globo, puntos, id);
    this.pintarMagnitud(puntos);
    if (!id) return;
    const punto = puntos.find((p) => p.id === id);
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

const ANCHO_TEXTURA = 4096;

async function texturaTierra(features: readonly PaisGlobo[]): Promise<string> {
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
