// Formato de números y fechas según el idioma del traductor (por defecto, español). Un dato desconocido
// es «ND» (en inglés «N/A»), nunca 0. Los instantes se muestran siempre en UTC.
import { T_ES, Traductor, localeDe } from '../i18n/traducir';

export const ND = 'ND';

/** Texto de «dato desconocido» en el idioma del traductor. */
export const textoNd = (t: Traductor = T_ES): string => t('formato.nd');

const esNumero = (v: number | null | undefined): v is number =>
  typeof v === 'number' && Number.isFinite(v);

/** Hasta `maxDecimales` decimales, sin ceros sobrantes. */
export function formatearDecimal(v: number | null | undefined, maxDecimales: number, t: Traductor = T_ES): string {
  if (!esNumero(v)) return textoNd(t);
  return new Intl.NumberFormat(localeDe(t.idioma), { maximumFractionDigits: maxDecimales }).format(v);
}

export function formatearEntero(v: number | null | undefined, t: Traductor = T_ES): string {
  return formatearDecimal(v, 0, t);
}

/** Magnitud con exactamente 1 decimal (2,1; 0,0). */
export function formatearMagnitud(v: number | null | undefined, t: Traductor = T_ES): string {
  if (!esNumero(v)) return textoNd(t);
  return new Intl.NumberFormat(localeDe(t.idioma), { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v);
}

export function formatearProfundidad(v: number | null | undefined, t: Traductor = T_ES): string {
  if (!esNumero(v)) return textoNd(t);
  return `${formatearDecimal(v, 1, t)} km`;
}

const dos = (n: number) => String(n).padStart(2, '0');

// Nombres fijos (no `Intl`) para que el texto no cambie según la versión de ICU del navegador.
const MESES_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** `02/11` en español, `2 Nov` en inglés (día y mes en UTC). */
export function diaMesUtc(f: Date, t: Traductor = T_ES): string {
  return t.idioma === 'en'
    ? `${f.getUTCDate()} ${MESES_EN[f.getUTCMonth()]}`
    : `${dos(f.getUTCDate())}/${dos(f.getUTCMonth() + 1)}`;
}

function parsear(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const f = new Date(iso);
  return Number.isNaN(f.getTime()) ? null : f;
}

/** `02/11/2026 15:41:58 UTC` en español; `2 Nov 2026 15:41:58 UTC` en inglés. */
export function formatearInstanteUtc(iso: string | null | undefined, t: Traductor = T_ES): string {
  const f = parsear(iso);
  if (!f) return textoNd(t);
  const fecha =
    t.idioma === 'en'
      ? `${diaMesUtc(f, t)} ${f.getUTCFullYear()}`
      : `${diaMesUtc(f, t)}/${f.getUTCFullYear()}`;
  const hora = `${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())}:${dos(f.getUTCSeconds())}`;
  return `${fecha} ${hora} UTC`;
}

/** `15:03:28 (13:03 UTC)`: hora local (o de `zona`) y la hora UTC entre paréntesis. */
export function formatearHoraConUtc(iso: string | null | undefined, zona?: string, t: Traductor = T_ES): string {
  const f = parsear(iso);
  if (!f) return textoNd(t);
  const local = new Intl.DateTimeFormat(localeDe(t.idioma), {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
    timeZone: zona,
  }).format(f);
  return `${local} (${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())} UTC)`;
}
