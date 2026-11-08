// Datos para el globo 3D (feature 008). Sin Angular ni three.js: solo transforma la respuesta de /eventos/mapa.
import { EventoMapa, PropiedadesEventoMapa } from '../modelos/api';
import { estiloCirculo } from './escalas';
import { formatearInstanteUtc, formatearMagnitud, formatearProfundidad } from './formato';

export const ANILLOS_MAX = 60;
export const RADIO_ANILLO_MIN = 2.5;
export const RADIO_ANILLO_MAX = 14;
/** Segundos que tarda un anillo en llegar a su radio máximo. */
const DURACION_ANILLO_S = 1.8;
const SIN_PAIS = 'Sin país asignado';

/** Color del pulso por magnitud; ND va en gris claro (no se trata como 0). */
export function colorPulso(magnitud: number | null): string {
  const m = magnitudValida(magnitud);
  if (m === null) return '#c8d0d8';
  if (m >= 6) return '#ff2e4d';
  if (m >= 4) return '#ff6b3d';
  return '#ffb347';
}

export interface PuntoGlobo {
  id: string;
  lat: number;
  lng: number;
  color: string;
  /** Altura sobre la superficie en radios terrestres. */
  altura: number;
  /** Radio del punto en grados. */
  radio: number;
  props: PropiedadesEventoMapa;
}

export interface AnilloGlobo {
  id: string;
  lat: number;
  lng: number;
  color: string;
  /** Radio máximo en grados. */
  radioMax: number;
  /** Grados por segundo. */
  velocidad: number;
  /** Milisegundos entre pulsaciones; la mitad de la duración deja dos ondas concéntricas a la vez. */
  periodo: number;
}

function magnitudValida(m: number | null): number | null {
  return m !== null && Number.isFinite(m) ? m : null;
}

function conCoordenadas(features: readonly EventoMapa[]): EventoMapa[] {
  return features.filter((f) => {
    const [lon, lat] = f.geometry.coordinates;
    return Number.isFinite(lon) && Number.isFinite(lat);
  });
}

export function puntosGlobo(features: readonly EventoMapa[]): PuntoGlobo[] {
  return conCoordenadas(features).map((f) => {
    const [lng, lat] = f.geometry.coordinates;
    const m = magnitudValida(f.properties.magnitud);
    const escala = m === null ? 0 : Math.min(Math.max(m, 0), 9);
    return {
      id: f.properties.event_id,
      lat,
      lng,
      color: estiloCirculo(f.properties.magnitud, f.properties.profundidad).color,
      altura: 0.004 + escala * 0.005,
      radio: 0.3 + escala * 0.1,
      props: f.properties,
    };
  });
}

export function anillosGlobo(
  features: readonly EventoMapa[],
  opciones: { movimientoReducido?: boolean; max?: number } = {},
): AnilloGlobo[] {
  if (opciones.movimientoReducido) return [];
  const max = opciones.max ?? ANILLOS_MAX;
  return conCoordenadas(features)
    .slice()
    .sort((a, b) => Date.parse(b.properties.ocurrencia) - Date.parse(a.properties.ocurrencia))
    .slice(0, max)
    .map((f) => {
      const [lng, lat] = f.geometry.coordinates;
      const m = magnitudValida(f.properties.magnitud);
      const radioMax =
        m === null
          ? RADIO_ANILLO_MIN
          : Math.min(Math.max(RADIO_ANILLO_MIN + 1.5 * m, RADIO_ANILLO_MIN), RADIO_ANILLO_MAX);
      return {
        id: f.properties.event_id,
        lat,
        lng,
        color: colorPulso(m),
        radioMax,
        velocidad: radioMax / DURACION_ANILLO_S,
        periodo: (DURACION_ANILLO_S * 1000) / 2,
      };
    });
}

/** El anillo nace opaco y se desvanece al abrirse (`t` va de 0 a 1). */
export function colorAnillo(hex: string): (t: number) => string {
  const n = Number.parseInt(hex.replace('#', ''), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return (t) => `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, 1 - t))})`;
}

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escaparHtml(texto: string): string {
  return texto.replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

/** Etiqueta al pasar el ratón. globe.gl la inserta como HTML: todo lo que viene de la API va escapado. */
export function etiquetaGlobo(p: PropiedadesEventoMapa): string {
  const lugar =
    !p.pais_nombre || p.pais_nombre === SIN_PAIS ? `${SIN_PAIS} (mar o fuera de fronteras)` : p.pais_nombre;
  const marca = p.sintetico ? '<span class="globo-etiqueta__marca">SINTÉTICO</span> ' : '';
  return (
    `<div class="globo-etiqueta">` +
    `<strong>${marca}M ${escaparHtml(formatearMagnitud(p.magnitud))}</strong>` +
    `<span>${escaparHtml(lugar)}</span>` +
    `<span>${escaparHtml(formatearInstanteUtc(p.ocurrencia))} · ${escaparHtml(formatearProfundidad(p.profundidad))}</span>` +
    `</div>`
  );
}
