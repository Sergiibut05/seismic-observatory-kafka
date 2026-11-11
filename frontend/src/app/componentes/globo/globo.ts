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
import { PanelUiStore } from '../../nucleo/panel-ui.store';
import { TemaService } from '../../nucleo/tema.service';
import { INTERVALOS_PROFUNDIDAD } from '../../puro/escalas';
import {
  PALETAS_MUNDO,
  PaletaMundo,
  altitudDesdeZoom,
  altitudParaAncho,
  normalizarLng,
  zoomDesdeAltitud,
} from '../../puro/mundo';
import { formatearInstanteUtc, formatearMagnitud } from '../../puro/formato';
import {
  AnilloGlobo,
  PaisGlobo,
  PuntoGlobo,
  SerieEscena,
  alturaColumna,
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
import { precargarGlobo, soportaWebgl, texturaTierra } from './precarga';

export const GLOBO_HABILITADO = new InjectionToken<boolean>('GLOBO_HABILITADO', {
  providedIn: 'root',
  factory: () => typeof navigator === 'undefined' || !/jsdom/i.test(navigator.userAgent),
});

const PIXEL_RATIO_MAX = 1.5;
/** Altitud mínima al abrir: aunque el plano estuviera muy cerca, el globo se reconoce como globo. */
const ALTITUD_APERTURA_MIN = 0.9;
/** Altura en px de la columna M7 en la leyenda. */
const LEYENDA_ALTO_PX = 34;
const SERIES: readonly { id: SerieEscena; clave: Clave; titulo: Clave }[] = [
  { id: 'hora', clave: 'escena.serie_hora', titulo: 'recuentos.hora_titulo' },
  { id: 'magnitud', clave: 'escena.serie_magnitud', titulo: 'distribuciones.grafico_magnitud' },
  {
    id: 'profundidad',
    clave: 'escena.serie_profundidad',
    titulo: 'distribuciones.grafico_profundidad',
  },
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
  private readonly ui = inject(PanelUiStore);
  private readonly temas = inject(TemaService);
  private readonly paleta = computed<PaletaMundo>(() => PALETAS_MUNDO[this.temas.tema()]);
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
  /** La leyenda enseña lo que se dibuja: columnas, con la misma proporción que en el globo. */
  protected readonly columnasLeyenda = [2, 5, 7].map((m) => ({
    etiqueta: `M${m}`,
    alto: Math.round((alturaColumna(m) / alturaColumna(7)) * LEYENDA_ALTO_PX),
  }));

  protected readonly esReplay = computed(() => this.store.vista().modo === 'replay');
  protected readonly cifras = computed(() => {
    const d = this.datos.comparacion().datos;
    return d ? cifrasComparacion(d, this.i18n.t()) : null;
  });

  protected readonly crudos = computed(() => this.datos.mapa().datos?.features ?? []);
  protected readonly corte = computed(() =>
    instanteCinta(this.posCinta() / 1000, Date.now(), this.crudos()),
  );
  protected readonly visibles = computed(() => recortarPorHora(this.crudos(), this.corte()));
  protected readonly marcas = computed(() => marcasCinta(this.crudos(), Date.now()));
  protected readonly etiquetaCorte = computed(() =>
    formatearInstanteUtc(this.corte(), this.i18n.t()),
  );
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
  private destruido = false;

  constructor() {
    // Pase lo que pase (también sin WebGL), el panel espera a este aviso para revelar la escena.
    afterNextRender(() => void this.iniciar().finally(() => this.ui.avisarGloboListo()));

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

    // Cambio de tema: fondo, atmósfera, textura y pulsos; la cámara y los datos no se tocan.
    effect(() => {
      const p = this.paleta();
      if (this.estado() !== 'listo') return;
      untracked(() => this.aplicarPaleta(p));
    });

    this.ui.capturarVista = () => this.guardarVista();
    this.destroyRef.onDestroy(() => {
      if (this.ui.capturarVista) this.ui.capturarVista = null;
      this.destruido = true;
      this.observador?.disconnect();
      this.visibilidad?.disconnect();
      document.removeEventListener('visibilitychange', this.alCambiarPestana);
      if (this.capa && this.globo && this.mallas) this.mallas.destruirCapa(this.capa, this.globo);
      this.globo?._destructor();
      this.globo = null;
      this.capa = null;
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
      // Normalmente ya está precargado (módulos, fronteras y textura del tema): no se espera nada.
      const { Globe, mallas, paises } = await precargarGlobo();
      const p0 = this.paleta();
      const textura = paises.length ? await texturaTierra(paises, p0) : null;
      if (this.destruido) return;
      this.mallas = mallas;
      this.paises = paises;
      // Sin animación de entrada propia: la hace la transición de vista desde el plano.
      const globo = new Globe(el, { animateIn: false })
        .backgroundColor(p0.fondo)
        .globeImageUrl(textura ?? '')
        .showAtmosphere(p0.atmosfera !== null)
        .atmosphereColor(p0.atmosfera ?? p0.fondo)
        .atmosphereAltitude(0.12)
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
        // País pulsado (011): realce neutro de tinta según el tema; el rojo queda para la selección.
        .polygonCapColor(() => this.paleta().paisRelleno)
        .polygonSideColor(() => this.paleta().paisLado)
        .polygonStrokeColor(() => this.paleta().paisBorde)
        .polygonAltitude(0.006)
        .polygonsTransitionDuration(0)
        .htmlLat('lat')
        .htmlLng('lng')
        .htmlAltitude('alt')
        .htmlElement((d: object) => this.nodoMagnitud(d as { texto: string }))
        .htmlTransitionDuration(0)
        .onGlobeClick((c: { lat: number; lng: number }, ev: MouseEvent) => this.alClicGlobo(c, ev));

      // Arranca mirando lo que miraba el plano y se asienta con un ligero alejamiento.
      const v = this.ui.vistaMundo;
      const altitud = Math.max(
        v.zoom === null ? altitudDesdeZoom(2) : altitudDesdeZoom(v.zoom),
        ALTITUD_APERTURA_MIN,
        altitudParaAncho(el.clientWidth, el.clientHeight),
      );
      const destino = { lat: v.lat, lng: normalizarLng(v.lng), altitude: altitud };
      if (this.movimientoReducido) globo.pointOfView(destino);
      else {
        globo.pointOfView({ ...destino, altitude: altitud * 0.82 });
        globo.pointOfView(destino, 1100);
      }

      globo.renderer().setPixelRatio(Math.min(devicePixelRatio || 1, PIXEL_RATIO_MAX));
      const material = globo.globeMaterial() as unknown as { color?: { set(c: string): void } };
      material.color?.set(textura ? '#ffffff' : p0.oceano);

      const controles = globo.controls() as unknown as {
        autoRotate: boolean;
        autoRotateSpeed: number;
        addEventListener(tipo: string, fn: () => void): void;
      };
      controles.autoRotate = !this.movimientoReducido;
      controles.autoRotateSpeed = 0.25;
      controles.addEventListener('start', () => (controles.autoRotate = false));
      // El plano retoma el centro y el zoom que tenga la cámara al volver.
      controles.addEventListener('end', () => this.guardarVista());

      this.globo = globo;
      this.capa = mallas.crearCapaColumnas(globo);
      mallas.aplicarTemaMallas(this.capa, temaMallas(p0));
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
      // Columnas y pulsos ya puestos antes de avisar: el efecto de `visibles` llegaría un ciclo tarde.
      this.pintar(this.visibles());
      if (textura) await this.esperarTextura(globo);
    } catch (e) {
      console.error(
        `service=panel result=error bloque=globo motivo="no se pudo iniciar" detalle="${String(e)}"`,
      );
      this.estado.set('sin-webgl');
    }
  }

  /** La textura se aplica al terminar de cargarse (three.js la pone en `map`): se espera sin depender del bucle de dibujo. */
  private async esperarTextura(globo: GlobeInstance): Promise<void> {
    const material = globo.globeMaterial() as unknown as { map?: { image?: unknown } | null };
    const limite = performance.now() + 1500;
    while (!material.map?.image && performance.now() < limite && !this.destruido) {
      await new Promise((ok) => setTimeout(ok, 16));
    }
  }

  /** Textura de la Tierra con la paleta del tema (cacheada: cambiar de tema no la vuelve a dibujar). */
  private aplicarTextura(globo: GlobeInstance, p: PaletaMundo): void {
    const material = globo.globeMaterial() as unknown as { color?: { set(c: string): void } };
    if (!this.paises.length) {
      material.color?.set(p.oceano);
      return;
    }
    void texturaTierra(this.paises, p).then((url) => {
      if (!url || this.globo !== globo || this.paleta() !== p) return;
      globo.globeImageUrl(url);
      material.color?.set('#ffffff');
    });
  }

  private aplicarPaleta(p: PaletaMundo): void {
    const globo = this.globo;
    if (!globo) return;
    globo
      .backgroundColor(p.fondo)
      .showAtmosphere(p.atmosfera !== null)
      .atmosphereColor(p.atmosfera ?? p.fondo);
    if (this.capa && this.mallas) this.mallas.aplicarTemaMallas(this.capa, temaMallas(p));
    this.aplicarTextura(globo, p);
    globo.polygonsData([...globo.polygonsData()]);
    this.pintar(this.visibles());
  }

  private pintar(features: readonly EventoMapa[]): void {
    if (!this.globo) return;
    const puntos = puntosGlobo(features);
    this.globo
      .pointsData(puntos)
      .ringsData(
        anillosGlobo(features, {
          movimientoReducido: this.movimientoReducido,
          tema: this.temas.tema(),
        }),
      );
    if (this.capa && this.mallas) {
      this.mallas.actualizarColumnas(
        this.capa,
        this.globo,
        puntos,
        this.store.eventoSeleccionado(),
      );
    }
    this.pintarMagnitud(puntos);
  }

  private pintarMagnitud(puntos: PuntoGlobo[]): void {
    if (!this.globo) return;
    const id = this.store.eventoSeleccionado();
    const p = id ? puntos.find((x) => x.id === id) : undefined;
    this.globo.htmlElementsData(
      p
        ? [
            {
              lat: p.lat,
              lng: p.lng,
              alt: p.altura + 0.02,
              texto: formatearMagnitud(p.props.magnitud, this.i18n.t()),
            },
          ]
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
    globo.pointOfView(
      { lat: punto.lat, lng: punto.lng, altitude: 1.4 },
      this.movimientoReducido ? 0 : 900,
    );
  }

  private guardarVista(): void {
    if (!this.globo || this.estado() !== 'listo') return;
    const pov = this.globo.pointOfView();
    if (!Number.isFinite(pov.lat) || !Number.isFinite(pov.lng)) return;
    this.ui.vistaMundo = {
      lat: Math.max(-80, Math.min(80, pov.lat)),
      lng: normalizarLng(pov.lng),
      zoom: zoomDesdeAltitud(pov.altitude),
    };
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

/** Aro, contorno de las columnas y luces según el fondo del tema. */
function temaMallas(p: PaletaMundo): { aro: string; contorno: string; luz: number } {
  const claro = p.atmosfera === null;
  return { aro: p.seleccion, contorno: claro ? '#1a1a1a' : '#070b12', luz: claro ? 0.55 : 1 };
}
