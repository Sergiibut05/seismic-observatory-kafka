// Datos para el globo 3D (008 + 010). Sin Angular ni three.js: transforma /eventos/mapa.
import { T_ES, Traductor } from '../i18n/traducir';
import { EventoMapa, PropiedadesEventoMapa } from '../modelos/api';
import { DatoBarra, etiquetaHoraUtc } from './barras';
import { INTERVALOS_PROFUNDIDAD, estiloCirculo } from './escalas';
import { formatearInstanteUtc, formatearMagnitud, formatearProfundidad } from './formato';
import { TEMA_POR_DEFECTO, Tema } from './tema';

export const ANILLOS_MAX = 60;
export const RADIO_ANILLO_MIN = 1.5;
export const RADIO_ANILLO_MAX = 7;
/** Segundos que tarda un anillo en llegar a su radio máximo. */
const DURACION_ANILLO_S = 1.8;
const SIN_PAIS = 'Sin país asignado';
export const VENTANA_CINTA_MS = 24 * 3600 * 1000;
/** Stub de columna sin magnitud: no se trata como M = 0. En radios terrestres. */
export const ALTURA_COLUMNA_ND = 0.008;
/**
 * Crecimiento cuadrático (011): M2 ≈ 0,034, M5 ≈ 0,108, M7 ≈ 0,19 radios. La Tierra sigue
 * siendo lo que se ve; antes M5 ya medía un tercio del radio y el globo parecía un erizo.
 */
const ALTURA_COLUMNA_BASE = 0.02;
const ALTURA_COLUMNA_POR_M2 = 0.0035;

/**
 * Pulsos en rojo de pluma (011). En papel, más oscuro cuanto mayor la magnitud; en noche, más
 * claro. ND en gris (no se trata como 0).
 */
export const COLORES_PULSO: Record<Tema, { bajo: string; medio: string; alto: string; nd: string }> = {
  papel: { bajo: '#E07A86', medio: '#C8102E', alto: '#7A0019', nd: '#9A9385' },
  noche: { bajo: '#FF9A90', medio: '#FF6B5E', alto: '#FFE3DF', nd: '#C8D0D8' },
};

export function colorPulso(magnitud: number | null, tema: Tema = TEMA_POR_DEFECTO): string {
  const c = COLORES_PULSO[tema];
  const m = magnitudValida(magnitud);
  if (m === null) return c.nd;
  if (m >= 6) return c.alto;
  if (m >= 4) return c.medio;
  return c.bajo;
}

/** Altura de la columna en radios terrestres. Un nulo no usa la escala de M = 0. */
export function alturaColumna(magnitud: number | null): number {
  const m = magnitudValida(magnitud);
  if (m === null) return ALTURA_COLUMNA_ND;
  const escala = Math.min(Math.max(m, 0), 9);
  return ALTURA_COLUMNA_BASE + escala * escala * ALTURA_COLUMNA_POR_M2;
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
      altura: alturaColumna(m),
      radio: 0.3 + escala * 0.1,
      props: f.properties,
    };
  });
}

export function anillosGlobo(
  features: readonly EventoMapa[],
  opciones: { movimientoReducido?: boolean; max?: number; tema?: Tema } = {},
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
        color: colorPulso(m, opciones.tema),
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
export function etiquetaGlobo(p: PropiedadesEventoMapa, t: Traductor = T_ES): string {
  const lugar = !p.pais_nombre || p.pais_nombre === SIN_PAIS ? t('dominio.sin_pais_mar') : p.pais_nombre;
  const marca = p.sintetico
    ? `<span class="globo-etiqueta__marca">${escaparHtml(t('dominio.sintetico'))}</span> `
    : '';
  return (
    `<div class="globo-etiqueta">` +
    `<strong>${marca}M ${escaparHtml(formatearMagnitud(p.magnitud, t))}</strong>` +
    `<span>${escaparHtml(lugar)}</span>` +
    `<span>${escaparHtml(formatearInstanteUtc(p.ocurrencia, t))} · ${escaparHtml(formatearProfundidad(p.profundidad, t))}</span>` +
    `</div>`
  );
}

/** Oculta lo posterior al corte. `null` o fecha inválida = sin recorte. */
export function recortarPorHora(
  features: readonly EventoMapa[],
  corte: string | null,
): EventoMapa[] {
  if (corte === null) return [...features];
  const t = Date.parse(corte);
  if (!Number.isFinite(t)) return [...features];
  return features.filter((f) => {
    const o = Date.parse(f.properties.ocurrencia);
    return Number.isFinite(o) && o <= t;
  });
}

export interface MarcaCinta {
  id: string;
  ocurrencia: string;
  /** 0 = inicio de la ventana (24 h atrás), 1 = fin. */
  t: number;
}

export function finCinta(features: readonly EventoMapa[], ahoraMs: number): number {
  let fin = ahoraMs;
  for (const f of features) {
    const o = Date.parse(f.properties.ocurrencia);
    if (Number.isFinite(o) && o > fin) fin = o;
  }
  return fin;
}

export function marcasCinta(features: readonly EventoMapa[], ahoraMs: number): MarcaCinta[] {
  const fin = finCinta(features, ahoraMs);
  const inicio = fin - VENTANA_CINTA_MS;
  return conCoordenadas(features).map((f) => {
    const o = Date.parse(f.properties.ocurrencia);
    const t = Number.isFinite(o) ? (o - inicio) / VENTANA_CINTA_MS : 0;
    return {
      id: f.properties.event_id,
      ocurrencia: f.properties.ocurrencia,
      t: Math.min(1, Math.max(0, t)),
    };
  });
}

/** Instante ISO del cursor de la cinta (`pos` de 0 a 1). */
export function instanteCinta(pos: number, ahoraMs: number, features: readonly EventoMapa[]): string {
  const fin = finCinta(features, ahoraMs);
  const inicio = fin - VENTANA_CINTA_MS;
  const p = Math.min(1, Math.max(0, pos));
  return new Date(inicio + p * VENTANA_CINTA_MS).toISOString();
}

export interface PaisGlobo {
  type: 'Feature';
  properties: { ADM0_A3: string | null };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] } | null;
}

/** Ray casting en un anillo GeoJSON [lng, lat][]. */
export function puntoEnAnillo(lng: number, lat: number, anillo: readonly number[][]): boolean {
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const xi = anillo[i][0];
    const yi = anillo[i][1];
    const xj = anillo[j][0];
    const yj = anillo[j][1];
    const cruza = yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + Number.EPSILON) + xi;
    if (cruza) dentro = !dentro;
  }
  return dentro;
}

function anillosDe(geometry: NonNullable<PaisGlobo['geometry']>): number[][][][] {
  return geometry.type === 'Polygon'
    ? [geometry.coordinates as number[][][]]
    : (geometry.coordinates as number[][][][]);
}

export function puntoEnPais(lng: number, lat: number, pais: PaisGlobo): boolean {
  if (!pais.geometry) return false;
  for (const poligono of anillosDe(pais.geometry)) {
    const [exterior, ...huecos] = poligono;
    if (!exterior || !puntoEnAnillo(lng, lat, exterior)) continue;
    if (huecos.some((h) => puntoEnAnillo(lng, lat, h))) continue;
    return true;
  }
  return false;
}

/** Primer país (orden del catálogo) que contiene el punto. Sin coincidencia: null. */
export function paisEnPunto(paises: readonly PaisGlobo[], lat: number, lng: number): PaisGlobo | null {
  for (const p of paises) {
    if (puntoEnPais(lng, lat, p)) return p;
  }
  return null;
}

export type SerieEscena = 'hora' | 'magnitud' | 'profundidad';

const BORDES_MAGNITUD = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

function intervalosMagnitud(): { desde: number | null; hasta: number | null; etiqueta: string }[] {
  const out: { desde: number | null; hasta: number | null; etiqueta: string }[] = [
    { desde: null, hasta: BORDES_MAGNITUD[0], etiqueta: `< ${BORDES_MAGNITUD[0]}` },
  ];
  for (let i = 0; i < BORDES_MAGNITUD.length - 1; i++) {
    const a = BORDES_MAGNITUD[i];
    const b = BORDES_MAGNITUD[i + 1];
    out.push({ desde: a, hasta: b, etiqueta: `${a}–${b}` });
  }
  const ultimo = BORDES_MAGNITUD[BORDES_MAGNITUD.length - 1];
  out.push({ desde: ultimo, hasta: null, etiqueta: `≥ ${ultimo}` });
  return out;
}

function contarEn(
  valores: readonly (number | null)[],
  intervalos: readonly { desde: number | null; hasta: number | null; etiqueta: string }[],
  t: Traductor,
): DatoBarra[] {
  const n = intervalos.map(() => 0);
  let sinValor = 0;
  for (const v of valores) {
    if (v === null || !Number.isFinite(v)) {
      sinValor += 1;
      continue;
    }
    const i = intervalos.findIndex(
      (iv) => (iv.desde === null || v >= iv.desde) && (iv.hasta === null || v < iv.hasta),
    );
    if (i >= 0) n[i] += 1;
  }
  const barras: DatoBarra[] = intervalos.map((iv, i) => ({
    clave: `i${i}`,
    etiqueta: iv.etiqueta,
    valor: n[i],
  }));
  barras.push({ clave: 'sin-valor', etiqueta: t('grafico.sin_valor'), valor: sinValor, sinValor: true });
  return barras;
}

/** Barras de la escena a partir de los eventos ya recortados (la cinta no llama a la API). */
export function barrasEscena(
  features: readonly EventoMapa[],
  serie: SerieEscena,
  finMs: number,
  t: Traductor = T_ES,
): DatoBarra[] {
  if (serie === 'hora') {
    const inicio = finMs - VENTANA_CINTA_MS;
    const recuento = new Map<number, number>();
    for (let h = 0; h < 24; h++) recuento.set(inicio + h * 3600_000, 0);
    for (const f of features) {
      const o = Date.parse(f.properties.ocurrencia);
      if (!Number.isFinite(o) || o < inicio || o > finMs) continue;
      const bucket = inicio + Math.floor((o - inicio) / 3600_000) * 3600_000;
      recuento.set(bucket, (recuento.get(bucket) ?? 0) + 1);
    }
    return [...recuento.entries()].map(([ms, valor]) => {
      const iso = new Date(ms).toISOString();
      return { clave: iso, etiqueta: etiquetaHoraUtc(iso, t), valor };
    });
  }
  if (serie === 'magnitud') {
    return contarEn(
      features.map((f) => f.properties.magnitud),
      intervalosMagnitud(),
      t,
    );
  }
  return contarEn(
    features.map((f) => f.properties.profundidad),
    INTERVALOS_PROFUNDIDAD.map((i) => ({ desde: i.desde, hasta: i.hasta, etiqueta: i.etiqueta })),
    t,
  );
}
