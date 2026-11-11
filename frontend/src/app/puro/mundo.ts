// Un solo mundo para el plano y el globo (011): misma geometría (Natural Earth) y mismos colores.
// Dos paletas: papel (atlas impreso) y noche. Espejo de --mundo-* en styles.css.
import { Tema } from './tema';

export interface PaletaMundo {
  oceano: string;
  tierra: string;
  frontera: string;
  /** Retícula cada 30°: apenas visible. */
  reticula: string;
  /** Contorno de los círculos del plano y su opacidad. */
  bordeCirculo: string;
  opacidadBorde: number;
  /** Fondo de la escena del globo. */
  fondo: string;
  atmosfera: string | null;
  seleccion: string;
  /** País pulsado en el globo (011): realce neutro de tinta, no el rojo de alerta. */
  paisRelleno: string;
  paisLado: string;
  paisBorde: string;
}

export const PALETAS_MUNDO: Record<Tema, PaletaMundo> = {
  papel: {
    oceano: '#c5d1cf',
    tierra: '#f7f3ea',
    frontera: '#6f685c',
    reticula: 'rgba(26, 26, 26, 0.08)',
    bordeCirculo: '#1a1a1a',
    opacidadBorde: 0.6,
    fondo: '#f4f1ea',
    atmosfera: null,
    seleccion: '#c8102e',
    paisRelleno: 'rgba(26, 26, 26, 0.16)',
    paisLado: 'rgba(26, 26, 26, 0.10)',
    paisBorde: '#1a1a1a',
  },
  noche: {
    oceano: '#08141e',
    tierra: '#22393c',
    frontera: '#4d6d70',
    reticula: 'rgba(232, 238, 243, 0.07)',
    bordeCirculo: '#e8eef3',
    opacidadBorde: 0.45,
    fondo: '#070b12',
    atmosfera: '#3d5f6b',
    seleccion: '#ffffff',
    paisRelleno: 'rgba(232, 238, 243, 0.22)',
    paisLado: 'rgba(232, 238, 243, 0.10)',
    paisBorde: '#ffffff',
  },
};

/** Vista compartida entre plano y globo para que el cambio de modo no pierda dónde se miraba. */
export interface VistaMundo {
  lat: number;
  lng: number;
  /** Zoom de Leaflet equivalente. */
  zoom: number;
}

/** `zoom: null` = aún nadie ha movido el mapa: se ajusta al ancho del contenedor. */
export const VISTA_MUNDO_INICIAL: Omit<VistaMundo, 'zoom'> & { zoom: number | null } = {
  lat: 20,
  lng: 0,
  zoom: null,
};

const ALTITUD_ZOOM_2 = 1.85;
const ALTITUD_MIN = 0.1;
const ALTITUD_MAX = 2.6;

/** Longitud en [-180, 180): Leaflet con `worldCopyJump` puede dar valores fuera. */
export function normalizarLng(lng: number): number {
  if (!Number.isFinite(lng)) return 0;
  return ((((lng + 180) % 360) + 360) % 360) - 180;
}

/** Altitud de cámara de globe.gl (radios terrestres) que muestra más o menos lo mismo que un zoom de Leaflet. */
export function altitudDesdeZoom(zoom: number): number {
  const z = Number.isFinite(zoom) ? zoom : 2;
  const a = ALTITUD_ZOOM_2 / 2 ** (z - 2);
  return Math.min(ALTITUD_MAX, Math.max(ALTITUD_MIN, a));
}

const FOV_VERTICAL_GRADOS = 50; // cámara de globe.gl

/**
 * Altitud mínima para que el globo entero quepa a lo ancho (con un 10 % de margen). Solo
 * importa en vertical: en apaisado el alto ya limita y la cámara por defecto lo respeta.
 */
export function altitudParaAncho(ancho: number, alto: number): number {
  if (!(ancho > 0) || !(alto > 0) || ancho >= alto) return 0;
  const tanH = Math.tan(((FOV_VERTICAL_GRADOS / 2) * Math.PI) / 180) * (ancho / alto) * 0.9;
  return 1 / Math.sin(Math.atan(tanH)) - 1;
}

/** Zoom de Leaflet que muestra el mundo entero a lo ancho de un contenedor (en medios niveles). */
export function zoomParaAncho(ancho: number, zoomMin = 1, zoomMax = 3): number {
  if (!(ancho > 0)) return 2;
  const z = Math.floor(Math.log2(ancho / 256) * 2) / 2;
  return Math.min(zoomMax, Math.max(zoomMin, z));
}

/** Inversa de `altitudDesdeZoom`, redondeada a medio nivel y dentro de los límites del plano. */
export function zoomDesdeAltitud(altitud: number, zoomMin = 1, zoomMax = 8): number {
  const a = Number.isFinite(altitud) && altitud > 0 ? altitud : ALTITUD_ZOOM_2;
  const z = 2 + Math.log2(ALTITUD_ZOOM_2 / a);
  return Math.min(zoomMax, Math.max(zoomMin, Math.round(z * 2) / 2));
}
