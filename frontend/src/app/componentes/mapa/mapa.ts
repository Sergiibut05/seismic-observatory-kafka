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
import { EventoMapa, RespuestaMapa } from '../../modelos/api';
import { FiltrosStore } from '../../nucleo/filtros.store';
import { PanelDatosService, bloqueConDatosAntiguos } from '../../nucleo/panel-datos.service';
import {
  INTERVALOS_PROFUNDIDAD,
  COLOR_ND,
  estiloCirculo,
  leyendaRadio,
} from '../../puro/escalas';
import { etiquetaDatosAntiguos } from '../../puro/etiqueta-antiguos';
import { formatearEntero } from '../../puro/formato';
import { crearFicha } from './mapa-ficha';

const URL_TESELAS = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATRIBUCION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">colaboradores de OpenStreetMap</a>';
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
  templateUrl: './mapa.html',
  styleUrl: './mapa.css',
  encapsulation: ViewEncapsulation.None, // la ficha y la leyenda de Leaflet viven fuera de la plantilla
})
export class Mapa {
  private readonly store = inject(FiltrosStore);
  private readonly datos = inject(PanelDatosService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly habilitado = inject(MAPA_HABILITADO);
  private readonly contenedor = viewChild<ElementRef<HTMLElement>>('lienzo');

  protected readonly bloque = this.datos.mapa;
  protected readonly respuesta = computed(() => this.bloque().datos);
  protected readonly antiguos = computed(() => bloqueConDatosAntiguos(this.bloque()));
  protected readonly etiquetaAntiguos = computed(() =>
    etiquetaDatosAntiguos(this.bloque().lecturaOk),
  );
  protected readonly truncado = computed(() => this.respuesta()?.truncado === true);
  protected readonly devueltos = computed(() => formatearEntero(this.respuesta()?.devueltos));
  protected readonly total = computed(() => formatearEntero(this.respuesta()?.total));

  protected readonly mapaDisponible = signal(this.habilitado);
  protected readonly errorFronteras = signal(false);
  protected readonly seleccionFuera = signal(false);
  protected readonly anuncio = signal('');

  protected readonly leyendaRadio = leyendaRadio();
  protected readonly intervalos = INTERVALOS_PROFUNDIDAD;
  protected readonly colorNd = COLOR_ND;

  private readonly listo = signal(false);
  private mapa: L.Map | null = null;
  private capa: L.FeatureGroup | null = null;
  private popup: L.Popup | null = null;
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
      L.control.zoom({ zoomInTitle: 'Acercar', zoomOutTitle: 'Alejar' }).addTo(mapa);
      mapa.attributionControl.setPrefix(
        '<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>',
      );
      L.tileLayer(URL_TESELAS, { maxZoom: 19, attribution: ATRIBUCION }).addTo(mapa);

      // Fronteras bajo los círculos: panel propio con su lienzo, sin depender del orden de carga.
      mapa.createPane('fronteras').style.zIndex = '350';
      this.capa = L.featureGroup().addTo(mapa);
      this.popup = L.popup({ maxWidth: 320, className: 'ficha-popup', autoPanPadding: [24, 24] });

      mapa.on('popupopen', (e: L.PopupEvent) => {
        const cerrar = e.popup.getElement()?.querySelector('.leaflet-popup-close-button');
        cerrar?.setAttribute('aria-label', 'Cerrar ficha');
        cerrar?.setAttribute('title', 'Cerrar ficha');
      });
      mapa.on('popupclose', () => {
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
    return {
      radius: est.radio,
      fillColor: est.color,
      fillOpacity: 0.85,
      color: seleccionado ? COLOR_SELECCION : COLOR_BORDE_CIRCULO,
      weight: seleccionado ? 4 : 1,
      dashArray: est.bordeDiscontinuo && !seleccionado ? '3 2' : undefined,
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
      const version = `${f.properties.updated}|${lon}|${lat}`;
      vigentes.add(id);
      const previo = this.dibujados.get(id);
      if (previo?.version === version) continue;
      if (previo) capa.removeLayer(previo.marcador);
      const marcador = L.circleMarker([lat, lon], this.estiloDe(f, id === seleccion));
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
      this.popup.setLatLng(posicion).setContent(crearFicha(d.evento.properties)).openOn(mapa);
    } finally {
      this.cerrandoPorCodigo = false;
    }
    this.fichaAbierta = version;
    if (!mapa.getBounds().contains(posicion)) mapa.panTo(posicion);
    this.anuncio.set(`Evento ${id} seleccionado; ficha abierta en el mapa.`);
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
  }
}
