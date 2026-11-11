// Texto de la frase de filtros (010). Sin Angular.
import { T_ES, Traductor } from '../i18n/traducir';
import { CampoFiltro, FiltrosAplicados, VistaDatos, nombreVisible } from './filtros';
import { formatearMagnitud } from './formato';

export type IdTrozo = 'modo' | 'magnitud' | 'pais' | 'ventana';

export interface TrozoFrase {
  id: IdTrozo;
  texto: string;
  campo: CampoFiltro | 'modo';
}

export function textoMagnitud(f: FiltrosAplicados, t: Traductor = T_ES): string {
  const min = f.magnitudMin;
  const max = f.magnitudMax;
  if (min === undefined && max === undefined) return t('frase.todas_magnitudes');
  if (min !== undefined && max !== undefined) {
    return t('frase.mag_rango', { min: formatearMagnitud(min, t), max: formatearMagnitud(max, t) });
  }
  if (min !== undefined) return t('frase.mag_min', { valor: formatearMagnitud(min, t) });
  return t('frase.mag_max', { valor: formatearMagnitud(max, t) });
}

export function textoVentana(f: FiltrosAplicados, t: Traductor = T_ES): string {
  if (!f.desde && !f.hasta) return t('frase.todo_periodo');
  if (f.desde && f.hasta) return `${f.desde} – ${f.hasta}`;
  return f.desde ?? f.hasta ?? t('frase.todo_periodo');
}

export function trozosFrase(
  vista: VistaDatos,
  f: FiltrosAplicados,
  t: Traductor = T_ES,
  nombrePais?: string,
): TrozoFrase[] {
  const pais = f.pais
    ? (nombrePais && nombrePais.length > 0 ? nombrePais : nombreVisible(f.pais, t))
    : t('frase.todos_paises');
  return [
    {
      id: 'modo',
      texto: vista.modo === 'replay' ? t('vista.replay') : t('vista.directo'),
      campo: 'modo',
    },
    { id: 'magnitud', texto: textoMagnitud(f, t), campo: 'magnitudMin' },
    { id: 'pais', texto: pais, campo: 'pais' },
    { id: 'ventana', texto: textoVentana(f, t), campo: 'desde' },
  ];
}
