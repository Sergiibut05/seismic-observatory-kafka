// Formato de números y fechas en español. Un dato desconocido es «ND», nunca 0.

export const ND = 'ND';

const esNumero = (v: number | null | undefined): v is number =>
  typeof v === 'number' && Number.isFinite(v);

/** Hasta `maxDecimales` decimales, sin ceros sobrantes. */
export function formatearDecimal(v: number | null | undefined, maxDecimales: number): string {
  if (!esNumero(v)) return ND;
  return new Intl.NumberFormat('es-ES', { maximumFractionDigits: maxDecimales }).format(v);
}

export function formatearEntero(v: number | null | undefined): string {
  return formatearDecimal(v, 0);
}

/** Magnitud con exactamente 1 decimal (2,1; 0,0). */
export function formatearMagnitud(v: number | null | undefined): string {
  if (!esNumero(v)) return ND;
  return new Intl.NumberFormat('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v);
}

export function formatearProfundidad(v: number | null | undefined): string {
  if (!esNumero(v)) return ND;
  return `${formatearDecimal(v, 1)} km`;
}

const dos = (n: number) => String(n).padStart(2, '0');

function parsear(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const f = new Date(iso);
  return Number.isNaN(f.getTime()) ? null : f;
}

/** `02/11/2026 15:41:58 UTC` */
export function formatearInstanteUtc(iso: string | null | undefined): string {
  const f = parsear(iso);
  if (!f) return ND;
  const fecha = `${dos(f.getUTCDate())}/${dos(f.getUTCMonth() + 1)}/${f.getUTCFullYear()}`;
  const hora = `${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())}:${dos(f.getUTCSeconds())}`;
  return `${fecha} ${hora} UTC`;
}

/** `15:03:28 (13:03 UTC)`: hora local (o de `zona`) y la hora UTC entre paréntesis. */
export function formatearHoraConUtc(iso: string | null | undefined, zona?: string): string {
  const f = parsear(iso);
  if (!f) return ND;
  const local = new Intl.DateTimeFormat('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
    timeZone: zona,
  }).format(f);
  return `${local} (${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())} UTC)`;
}
