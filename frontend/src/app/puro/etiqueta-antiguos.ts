// Texto de un bloque que no pudo actualizarse y conserva su última lectura correcta (FR-011).
import { formatearHoraConUtc, ND } from './formato';

/** `datos del 15:03:28 (13:03 UTC), desactualizados` (o «ND» si no hay hora de lectura). */
export function etiquetaDatosAntiguos(lecturaOkMs: number | null, zona?: string): string {
  if (lecturaOkMs === null || !Number.isFinite(lecturaOkMs)) return `datos de ${ND}, desactualizados`;
  const hora = formatearHoraConUtc(new Date(lecturaOkMs).toISOString(), zona);
  return `datos del ${hora}, desactualizados`;
}
