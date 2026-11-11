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
import * as L from 'leaflet';
import { I18nService } from '../../i18n/i18n.service';
import { EventoMapa, RespuestaMapa } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService, bloqueConDatosAntiguos } from '../../nucleo/panel-datos.service';
import {
  INTERVALOS_PROFUNDIDAD,
  COLOR_ND,
  contornoCirculo,
  estiloCirculo,
  leyendaRadio,
} from '../../puro/escalas';
import { etiquetaDatosAntiguos } from '../../puro/etiqueta-antiguos';
import { PanelUiStore } from '../../nucleo/panel-ui.store';
import { Globo } from '../globo/globo';
import { crearFicha, crearResumen } from './mapa-ficha';

const URL_TESELAS = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const atribucion = (colaboradores: string) =>
  `© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">${colaboradores}</a>`;
const URL_FRONTERAS = 'datos/paises.geojson';
const COLOR_BORDE_CIRCULO = '#0f1a24'; // = --borde-circulo
const COLOR_SELECCION = '#ffd166';

/**
 * jsdom no tiene canvas ni layout: allí Leaflet no se inicia (el dibujo se comprueba en
 * navegador real, T11). En un navegador es siempre `true`.
 */
export const MAPA_HABILITADO = new InjectionToken<boolean>('MAPA_HABILITADO', {
  providedIn: 'root',
  factory: () => typeof navigator === 'undefined' || !/jsdom/i.test(navigator.userAgent),
});

/** Un círculo dibujado y la versión del evento que representa. */
interface Dibujado {
  marcador: L.CircleMarker;
  version: string;
  evento: EventoMapa;
}

/**
 * Mapa de eventos (FR-001). Una sola instancia de Leaflet y una sola capa de círculos que se
 * actualiza por diferencias en cada refresco: sin parpadeo y sin tocar zoom ni centro.
 */
@Component({
  selector: 'app-mapa',
  imports: [Globo],
  templateUrl: './mapa.html',
  styleUrl: './mapa.css',
  encapsulation: ViewEncapsulation.None, // la ficha y la leyenda de Leaflet viven fuera de la plantilla
})
export class Mapa {
  private readonly store = inject(FiltrosStore);
  protected readonly ui = inject(PanelUiStore);
  private readonly datos = inject(PanelDatosService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly habilitado = inject(MAPA_HABILITADO);
  protected readonly i18n = inject(I18nService);
  private readonly contenedor = viewChild<ElementRef<HTMLElement>>('lienzo');

  protected readonly bloque = this.datos.mapa;
  protected readonly respuesta = computed(() => this.bloque().datos);
  protected readonly antiguos = computed(() => bloqueConDatosAntiguos(this.bloque()));
  protected readonly etiquetaAntiguos = computed(() =>
    etiquetaDatosAntiguos(this.bloque().lecturaOk, undefined, this.i18n.t()),
  );
  /** La rotulación sigue a los datos recibidos (modo de la respuesta), no a lo recién elegido. */
  protected readonly esReplay = computed(() => this.respuesta()?.modo === 'replay');
  protected readonly sinteticos = computed(() => this.store.vista().sinteticos);
  protected readonly truncado = computed(() => this.respuesta()?.truncado === true);
  protected readonly devueltos = computed(() => this.i18n.entero(this.respuesta()?.devueltos));
  protected readonly total = computed(() => this.i18n.entero(this.respuesta()?.total));

  protected readonly mapaDisponible = signal(this.habilitado);
  protected readonly errorFronteras = signal(false);
  protected readonly seleccionFuera = signal(false);
  /** Evento cuya ficha se acaba de abrir; el aviso para lectores de pantalla sigue al idioma. */
  private readonly eventoAnunciado = signal<string | null>(null);
  protected readonly anuncio = computed(() => {
    const id = this.eventoAnunciado();
    return id === null ? '' : this.i18n.tr('mapa.anuncio', { id });
  });
  /** Vista 3D opcional (008/010); el plano es la vista por defecto y Leaflet sigue vivo debajo. */
  protected readonly enGlobo = this.ui.enGlobo;
  /** La ficha vive dentro del panel de Leaflet (z-index 400): con ella abierta, la leyenda se aparta para no taparla. */
  protected readonly fichaVisible = signal(false);

  protected readonly radiosLeyenda = leyendaRadio().filter((r) => ['2', '4', '6', '8'].includes(r.etiqueta));
  protected readonly intervalos = INTERVALOS_PROFUNDIDAD;
  protected readonly colorNd = COLOR_ND;

  private readonly listo = signal(false);
  private mapa: L.Map | null = null;
  private capa: L.FeatureGroup | null = null;
  private popup: L.Popup | null = null;
  private controlZoom: L.Control.Zoom | null = null;
  /** Texto de atribución puesto en el control, para quitarlo exactamente al cambiar de idioma. */
  private atribucionPuesta: string | null = null;
  private fichaAbierta: string | null = null;
  private cerrandoPorCodigo = false;
  private readonly dibujados = new Map<string, Dibujado>();
  private observador: ResizeObserver | null = null;
  private temporizadorTamano: ReturnType<typeof setTimeout> | null = null;
  private destruido = false;

  constructor() {
    afterNextRender(() => this.iniciar());

    // Datos nuevos → diferencias sobre la capa existente.
    effect(() => {
      if (!this.listo()) return;
      const datos = this.respuesta();
      untracked(() => this.sincronizar(datos));
    });

    // Selección (tabla ↔ mapa).
    effect(() => {
      const id = this.store.eventoSeleccionado();
      if (!this.listo()) return;
      untracked(() => this.aplicarSeleccion(id));
    });

    // Cambio de idioma: se repinta lo que Leaflet escribe fuera de la plantilla (resumen, ficha, controles),
    // con los datos ya cargados y sin pedir nada a la API.
    effect(() => {
      this.i18n.idioma();
      if (!this.listo()) return;
      untracked(() => this.repintarTextos());
    });

    this.destroyRef.onDestroy(() => this.destruir());
  }

  private iniciar(): void {
    const el = this.contenedor()?.nativeElement;
    if (!this.habilitado || !el || this.destruido) return;
    try {
      const mapa = L.map(el, {
        preferCanvas: true,
        zoomControl: false,
        worldCopyJump: true,
        minZoom: 2,
        center: [20, 0],
        zoom: 2,
      });
      this.controlZoom = L.control
        .zoom({ zoomInTitle: this.i18n.tr('mapa.acercar'), zoomOutTitle: this.i18n.tr('mapa.alejar') })
        .addTo(mapa);
      mapa.attributionControl.setPrefix(
        '<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>',
      );
      // La atribución se pone en el control (no en la capa) para poder cambiarla de idioma.
      L.tileLayer(URL_TESELAS, { maxZoom: 19 }).addTo(mapa);
      this.ponerAtribucion(mapa);

      // Fronteras bajo los círculos: panel propio con su lienzo, sin depender del orden de carga.
      mapa.createPane('fronteras').style.zIndex = '350';
      this.capa = L.featureGroup().addTo(mapa);
      this.popup = L.popup({
        minWidth: 240,
        maxWidth: 300,
        className: 'ficha-popup',
        autoPanPadding: [24, 24],
      });

      mapa.on('popupopen', (e: L.PopupEvent) => {
        this.rotularCierre(e.popup.getElement());
        this.fichaVisible.set(true);
      });
      mapa.on('popupclose', () => {
        this.fichaVisible.set(false);
        if (this.cerrandoPorCodigo) return;
        this.fichaAbierta = null;
        this.store.eventoSeleccionado.set(null);
      });

      this.mapa = mapa;
      this.observador = new ResizeObserver(() => this.reajustar());
      this.observador.observe(el);
      this.reajustar();
      void this.cargarFronteras(mapa);
      this.listo.set(true);
    } catch (e) {
      console.error(`service=panel result=error bloque=mapa motivo="no se pudo iniciar Leaflet" detalle="${String(e)}"`);
      this.mapaDisponible.set(false);
    }
  }

  private ponerAtribucion(mapa: L.Map): void {
    const control = mapa.attributionControl;
    if (this.atribucionPuesta !== null) control.removeAttribution(this.atribucionPuesta);
    this.atribucionPuesta = atribucion(this.i18n.tr('mapa.osm'));
    control.addAttribution(this.atribucionPuesta);
  }

  private rotularCierre(popup: HTMLElement | undefined): void {
    const cerrar = popup?.querySelector('.leaflet-popup-close-button');
    const texto = this.i18n.tr('mapa.cerrar_ficha');
    cerrar?.setAttribute('aria-label', texto);
    cerrar?.setAttribute('title', texto);
  }

  /** Textos que Leaflet guarda fuera de la plantilla: se rehacen con el traductor vigente. */
  private repintarTextos(): void {
    const mapa = this.mapa;
    if (!mapa) return;
    const t = this.i18n.t();

    const contenedorZoom = this.controlZoom?.getContainer();
    const rotulos: [string, string][] = [
      ['.leaflet-control-zoom-in', t('mapa.acercar')],
      ['.leaflet-control-zoom-out', t('mapa.alejar')],
    ];
    for (const [selector, texto] of rotulos) {
      const enlace = contenedorZoom?.querySelector(selector);
      enlace?.setAttribute('title', texto);
      enlace?.setAttribute('aria-label', texto);
    }
    this.ponerAtribucion(mapa);

    for (const d of this.dibujados.values()) {
      d.marcador.setTooltipContent(crearResumen(d.evento.properties, document, t));
    }
    // Ficha abierta: se cambia su contenido sin cerrarla ni mover el mapa.
    if (this.fichaAbierta !== null && this.popup?.isOpen()) {
      const id = this.store.eventoSeleccionado();
      const d = id === null ? undefined : this.dibujados.get(id);
      if (d) {
        this.popup.setContent(crearFicha(d.evento.properties, document, t));
        this.rotularCierre(this.popup.getElement());
      }
    }
  }

  /** Las fronteras se piden una sola vez; si fallan, el mapa sigue con los círculos. */
  private async cargarFronteras(mapa: L.Map): Promise<void> {
    try {
      const r = await fetch(URL_FRONTERAS);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const geo = (await r.json()) as GeoJSON.GeoJsonObject;
      if (this.destruido || this.mapa !== mapa) return;
      // `renderer` se reenvía a cada polígono pero @types/leaflet no lo declara en GeoJSONOptions.
      const opciones: L.GeoJSONOptions & { renderer: L.Renderer } = {
        pane: 'fronteras',
        renderer: L.canvas({ pane: 'fronteras' }),
        interactive: false,
        style: { color: '#5b6b78', weight: 0.8, fill: true, fillColor: '#f6f4ee', fillOpacity: 0.35 },
      };
      L.geoJSON(geo, opciones).addTo(mapa);
    } catch (e) {
      console.warn(`service=panel result=error bloque=fronteras motivo="no se pudo cargar" detalle="${String(e)}"`);
      if (!this.destruido) this.errorFronteras.set(true);
    }
  }

  private reajustar(): void {
    if (this.temporizadorTamano !== null) return;
    this.temporizadorTamano = setTimeout(() => {
      this.temporizadorTamano = null;
      this.mapa?.invalidateSize({ pan: false });
    }, 50);
  }

  private estiloDe(e: EventoMapa, seleccionado: boolean): L.CircleMarkerOptions {
    const est = estiloCirculo(e.properties.magnitud, e.properties.profundidad);
    const contorno = contornoCirculo(e.properties.sintetico, est.bordeDiscontinuo);
    return {
      radius: est.radio,
      fillColor: est.color,
      fillOpacity: 0.85,
      color: seleccionado ? COLOR_SELECCION : COLOR_BORDE_CIRCULO,
      weight: seleccionado ? 4 : contorno.grosor,
      dashArray: seleccionado ? undefined : contorno.discontinuo,
    };
  }

  private sincronizar(datos: RespuestaMapa | null): void {
    const capa = this.capa;
    if (!capa || !datos) return;
    const vigentes = new Set<string>();
    const seleccion = this.store.eventoSeleccionado();

    for (const f of datos.features) {
      const [lon, lat] = f.geometry.coordinates;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
      const id = f.properties.event_id;
      const { updated, sintetico, reproducido_en } = f.properties;
      const version = `${updated}|${lon}|${lat}|${sintetico}|${reproducido_en}`;
      vigentes.add(id);
      const previo = this.dibujados.get(id);
      if (previo?.version === version) continue;
      if (previo) capa.removeLayer(previo.marcador);
      const marcador = L.circleMarker([lat, lon], this.estiloDe(f, id === seleccion));
      marcador.bindTooltip(crearResumen(f.properties, document, this.i18n.t()), {
        direction: 'top',
        offset: [0, -4],
        className: 'mapa-resumen',
      });
      marcador.on('click', () => this.store.eventoSeleccionado.set(id));
      capa.addLayer(marcador);
      this.dibujados.set(id, { marcador, version, evento: f });
    }
    for (const [id, d] of this.dibujados) {
      if (vigentes.has(id)) continue;
      capa.removeLayer(d.marcador);
      this.dibujados.delete(id);
    }
    this.aplicarSeleccion(seleccion);
  }

  private anterior: string | null = null;

  private aplicarSeleccion(id: string | null): void {
    const mapa = this.mapa;
    if (!mapa || !this.popup) return;

    if (this.anterior && this.anterior !== id) {
      const d = this.dibujados.get(this.anterior);
      if (d) d.marcador.setStyle(this.estiloDe(d.evento, false));
    }
    this.anterior = id;

    if (id === null) {
      this.seleccionFuera.set(false);
      this.cerrarFicha();
      return;
    }
    const d = this.dibujados.get(id);
    if (!d) {
      this.seleccionFuera.set(true);
      this.cerrarFicha();
      return;
    }
    this.seleccionFuera.set(false);
    d.marcador.setStyle(this.estiloDe(d.evento, true));
    d.marcador.bringToFront();

    const version = `${id}|${d.version}`;
    if (this.fichaAbierta === version) return;
    const posicion = d.marcador.getLatLng();
    this.cerrandoPorCodigo = true;
    try {
      this.popup
        .setLatLng(posicion)
        .setContent(crearFicha(d.evento.properties, document, this.i18n.t()))
        .openOn(mapa);
    } finally {
      this.cerrandoPorCodigo = false;
    }
    this.fichaAbierta = version;
    if (!mapa.getBounds().contains(posicion)) mapa.panTo(posicion);
    this.eventoAnunciado.set(id);
  }

  private cerrarFicha(): void {
    if (!this.mapa || this.fichaAbierta === null) return;
    this.cerrandoPorCodigo = true;
    try {
      this.mapa.closePopup();
    } finally {
      this.cerrandoPorCodigo = false;
    }
    this.fichaAbierta = null;
  }

  private destruir(): void {
    this.destruido = true;
    this.observador?.disconnect();
    this.observador = null;
    if (this.temporizadorTamano !== null) clearTimeout(this.temporizadorTamano);
    this.temporizadorTamano = null;
    this.dibujados.clear();
    this.mapa?.off();
    this.mapa?.remove();
    this.mapa = null;
    this.capa = null;
    this.popup = null;
    this.controlZoom = null;
  }
}
