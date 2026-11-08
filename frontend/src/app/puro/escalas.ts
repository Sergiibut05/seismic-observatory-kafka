// Escalas visuales del mapa y su leyenda: fuente única de radio y color.
// Los colores se repiten como variables CSS (`--prof-*` en styles.css) para la leyenda
// HTML; si cambian aquí, cambian allí.
import { T_ES, Traductor } from '../i18n/traducir';

export const ETIQUETA_ND = 'ND';
/** Radio fijo (px) de un evento sin magnitud: distinto del de M = 0 (3 px). */
export const RADIO_ND = 5;
export const COLOR_ND = '#8d9399';

const RADIO_BASE = 3;
const RADIO_POR_MAGNITUD = 2.5;
const MAGNITUD_MAX_ESCALA = 8;

function esNumero(v: number | null): v is number {
  return v !== null && Number.isFinite(v);
}

export function radioPorMagnitud(magnitud: number | null): number {
  if (!esNumero(magnitud)) return RADIO_ND;
  const m = Math.min(Math.max(magnitud, 0), MAGNITUD_MAX_ESCALA);
  return RADIO_BASE + RADIO_POR_MAGNITUD * m;
}

export interface IntervaloProfundidad {
  /** Inclusivo; `null` = abierto por debajo. */
  desde: number | null;
  /** Exclusivo; `null` = abierto por encima. */
  hasta: number | null;
  etiqueta: string;
  color: string;
}

/**
 * Mismos intervalos y etiquetas que `/distribuciones/profundidad`. Rampa secuencial
 * (amarillo claro = somero, azul marino = profundo), legible con daltonismo; lo negativo
 * (por encima del nivel de referencia) lleva un magenta propio.
 */
export const INTERVALOS_PROFUNDIDAD: readonly IntervaloProfundidad[] = [
  { desde: null, hasta: 0, etiqueta: '< 0', color: '#c2185b' },
  { desde: 0, hasta: 10, etiqueta: '0–10', color: '#ffffb2' },
  { desde: 10, hasta: 30, etiqueta: '10–30', color: '#d9f0a3' },
  { desde: 30, hasta: 70, etiqueta: '30–70', color: '#addd8e' },
  { desde: 70, hasta: 150, etiqueta: '70–150', color: '#41b6c4' },
  { desde: 150, hasta: 300, etiqueta: '150–300', color: '#1d91c0' },
  { desde: 300, hasta: 500, etiqueta: '300–500', color: '#225ea8' },
  { desde: 500, hasta: 700, etiqueta: '500–700', color: '#253494' },
  { desde: 700, hasta: null, etiqueta: '≥ 700', color: '#081d58' },
];

export function intervaloProfundidad(profundidad: number | null): IntervaloProfundidad | null {
  if (!esNumero(profundidad)) return null;
  return (
    INTERVALOS_PROFUNDIDAD.find(
      (i) => (i.desde === null || profundidad >= i.desde) && (i.hasta === null || profundidad < i.hasta),
    ) ?? null
  );
}

export function colorPorProfundidad(profundidad: number | null): string {
  return intervaloProfundidad(profundidad)?.color ?? COLOR_ND;
}

export interface EstiloCirculo {
  radio: number;
  color: string;
  /** Un valor desconocido se marca además con borde discontinuo (no solo por color). */
  bordeDiscontinuo: boolean;
  etiquetaMagnitud: string | null;
  etiquetaProfundidad: string | null;
}

export function estiloCirculo(
  magnitud: number | null,
  profundidad: number | null,
  t: Traductor = T_ES,
): EstiloCirculo {
  const sinMagnitud = !esNumero(magnitud);
  const sinProfundidad = !esNumero(profundidad);
  const nd = t('formato.nd');
  return {
    radio: radioPorMagnitud(magnitud),
    color: colorPorProfundidad(profundidad),
    bordeDiscontinuo: sinMagnitud || sinProfundidad,
    etiquetaMagnitud: sinMagnitud ? nd : null,
    etiquetaProfundidad: sinProfundidad ? nd : null,
  };
}

export interface EntradaLeyendaRadio {
  etiqueta: string;
  radio: number;
}

export function leyendaRadio(t: Traductor = T_ES): EntradaLeyendaRadio[] {
  return [0, 2, 4, 6, 8]
    .map((m) => ({ etiqueta: String(m), radio: radioPorMagnitud(m) }))
    .concat([{ etiqueta: t('formato.nd'), radio: RADIO_ND }]);
}

export interface ContornoCirculo {
  grosor: number;
  /** Patrón dashArray de Leaflet; undefined = línea continua. */
  discontinuo: string | undefined;
}

/**
 * Contorno del círculo. ND: fino y discontinuo. Caso sintético: grueso y con trazo más largo,
 * para que no se confunda con ND ni con un terremoto real (no depende solo del color).
 */
export function contornoCirculo(sintetico: boolean, bordeDiscontinuo: boolean): ContornoCirculo {
  if (sintetico) return { grosor: 2.5, discontinuo: '7 4' };
  return { grosor: 1, discontinuo: bordeDiscontinuo ? '3 2' : undefined };
}