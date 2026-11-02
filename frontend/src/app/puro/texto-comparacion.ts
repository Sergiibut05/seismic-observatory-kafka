// Textos de la comparación histórica (T8). Sin Angular. Lo desconocido es «no disponible» o «ND»,
// nunca 0.
import { ComparacionHistorica, FiltrosEfectivos } from '../modelos/api';
import { formatearDecimal, formatearEntero, formatearMagnitud } from './formato';

export const NO_DISPONIBLE = 'no disponible';

/** Aviso de respaldo cuando aún no hay respuesta de la API: el aviso debe verse siempre. */
export const AVISO_PERIODO_INCOMPLETO =
  'El último periodo puede estar incompleto: USGS publica con retraso y revisa los eventos después.';

/** «magnitud ≥ 4,0 · país: todos · subregión: todas» a partir de los filtros efectivos de la API. */
export function describirFiltrosEfectivos(f: FiltrosEfectivos): string {
  const mag =
    f.magnitud_min === null && f.magnitud_max === null
      ? 'magnitud: sin límites'
      : [
          f.magnitud_min !== null ? `magnitud ≥ ${formatearMagnitud(f.magnitud_min)}` : null,
          f.magnitud_max !== null ? `magnitud ≤ ${formatearMagnitud(f.magnitud_max)}` : null,
        ]
          .filter((t) => t !== null)
          .join(' y ');
  return `${mag} · país: ${f.pais ?? 'todos'} · subregión: ${f.subregion ?? 'todas'}`;
}

export interface CifrasComparacion {
  ultimas24h: string;
  mediaDiaria2025: string;
  eventos2025: string;
  cociente: string;
  /** `true` si el histórico no está cargado o falta la media: nada se pinta como 0. */
  historicoNoDisponible: boolean;
}

export function cifrasComparacion(c: ComparacionHistorica): CifrasComparacion {
  const h = c.historico_2025;
  const noDisp = h.estado !== 'cargado' || h.media_diaria === null;
  return {
    ultimas24h: formatearEntero(c.ventana_actual.eventos),
    mediaDiaria2025: noDisp ? NO_DISPONIBLE : formatearDecimal(h.media_diaria, 1),
    eventos2025: h.estado !== 'cargado' || h.eventos === null ? NO_DISPONIBLE : formatearEntero(h.eventos),
    cociente: noDisp || c.cociente === null ? NO_DISPONIBLE : formatearDecimal(c.cociente, 2),
    historicoNoDisponible: noDisp,
  };
}
