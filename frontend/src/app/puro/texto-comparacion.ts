// Textos de la comparación histórica (T8). Sin Angular. Lo desconocido es «no disponible» o «ND»,
// nunca 0.
import { T_ES, Traductor } from '../i18n/traducir';
import { ComparacionHistorica, FiltrosEfectivos } from '../modelos/api';
import { SIN_PAIS } from './filtros';
import { formatearDecimal, formatearEntero, formatearMagnitud } from './formato';

export const NO_DISPONIBLE = 'no disponible';

/** Aviso de respaldo cuando aún no hay respuesta de la API: el aviso debe verse siempre. */
export const AVISO_PERIODO_INCOMPLETO =
  'El último periodo puede estar incompleto: USGS publica con retraso y revisa los eventos después.';

/** «magnitud ≥ 4,0 · país: todos · subregión: todas» a partir de los filtros efectivos de la API. */
export function describirFiltrosEfectivos(f: FiltrosEfectivos, t: Traductor = T_ES): string {
  const mag =
    f.magnitud_min === null && f.magnitud_max === null
      ? t('comparacion.f_sin_limites')
      : [
          f.magnitud_min !== null
            ? t('comparacion.f_min', { valor: formatearMagnitud(f.magnitud_min, t) })
            : null,
          f.magnitud_max !== null
            ? t('comparacion.f_max', { valor: formatearMagnitud(f.magnitud_max, t) })
            : null,
        ]
          .filter((x) => x !== null)
          .join(` ${t('comparacion.f_y')} `);
  // El código de país no se traduce; la etiqueta fija «Sin país asignado» sí.
  const pais = f.pais === null ? t('comparacion.f_todos') : f.pais === SIN_PAIS ? t('dominio.sin_pais') : f.pais;
  return t('comparacion.f_completo', {
    magnitud: mag,
    pais,
    subregion:
      f.subregion === null
        ? t('comparacion.f_todas')
        : f.subregion === SIN_PAIS
          ? t('dominio.sin_pais')
          : f.subregion,
  });
}

export interface CifrasComparacion {
  ultimas24h: string;
  mediaDiaria2025: string;
  eventos2025: string;
  cociente: string;
  /** `true` si el histórico no está cargado o falta la media: nada se pinta como 0. */
  historicoNoDisponible: boolean;
}

export function cifrasComparacion(c: ComparacionHistorica, t: Traductor = T_ES): CifrasComparacion {
  const h = c.historico_2025;
  const noDisp = h.estado !== 'cargado' || h.media_diaria === null;
  const noDisponible = t('comparacion.no_disponible');
  return {
    ultimas24h: formatearEntero(c.ventana_actual.eventos, t),
    mediaDiaria2025: noDisp ? noDisponible : formatearDecimal(h.media_diaria, 1, t),
    eventos2025: h.estado !== 'cargado' || h.eventos === null ? noDisponible : formatearEntero(h.eventos, t),
    cociente: noDisp || c.cociente === null ? noDisponible : formatearDecimal(c.cociente, 2, t),
    historicoNoDisponible: noDisp,
  };
}
