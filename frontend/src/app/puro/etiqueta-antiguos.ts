// Texto de un bloque que no pudo actualizarse y conserva su última lectura correcta (FR-011).
import { T_ES, Traductor } from '../i18n/traducir';
import { formatearHoraConUtc, textoNd } from './formato';

/** `datos del 15:03:28 (13:03 UTC), desactualizados` (o «ND» si no hay hora de lectura). */
export function etiquetaDatosAntiguos(lecturaOkMs: number | null, zona?: string, t: Traductor = T_ES): string {
  if (lecturaOkMs === null || !Number.isFinite(lecturaOkMs)) {
    return t('etiqueta.antiguos_nd', { nd: textoNd(t) });
  }
  const hora = formatearHoraConUtc(new Date(lecturaOkMs).toISOString(), zona, t);
  return t('etiqueta.antiguos', { hora });
}
