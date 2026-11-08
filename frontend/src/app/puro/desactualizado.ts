// Cuándo avisar de que los datos no son frescos. Sin Angular.
import { T_ES, Traductor } from '../i18n/traducir';
import { EstadoApi } from '../modelos/api';

/** Una lectura correcta con más de 60 s (un ciclo de refresco) se marca como antigua. */
export const UMBRAL_LECTURA_ANTIGUA_MS = 60_000;

export type CodigoAviso = 'api_sin_respuesta' | 'base_fallida' | 'datos_desactualizados';

export interface Aviso {
  codigo: CodigoAviso;
  texto: string;
}

export interface ResultadoEstado {
  avisos: Aviso[];
}

/** Texto del aviso en el idioma del traductor (el `texto` guardado en `Aviso` es el del idioma con que se calculó). */
export function textoAviso(codigo: CodigoAviso, t: Traductor = T_ES): string {
  switch (codigo) {
    case 'api_sin_respuesta':
      return t('avisos.api_sin_respuesta');
    case 'base_fallida':
      return t('avisos.base_fallida');
    case 'datos_desactualizados':
      return t('avisos.datos_desactualizados');
  }
}

const aviso = (codigo: CodigoAviso, t: Traductor): Aviso => ({ codigo, texto: textoAviso(codigo, t) });

/**
 * Deriva los avisos del estado del sistema (FR-008).
 * @param ultimo  última respuesta correcta de `/status` (o `null` si no hubo ninguna)
 * @param fallo   `true` si la última consulta de `/status` falló
 */
export function calcularEstado(
  ultimo: EstadoApi | null,
  fallo: boolean,
  t: Traductor = T_ES,
): ResultadoEstado {
  // Con la API caída no sabemos nada actual: un único aviso, sin mezclar lecturas viejas.
  if (fallo) return { avisos: [aviso('api_sin_respuesta', t)] };
  if (!ultimo) return { avisos: [] };
  const avisos: Aviso[] = [];
  if (ultimo.base_de_datos === 'fallida') avisos.push(aviso('base_fallida', t));
  if (ultimo.datos_desactualizados === true) avisos.push(aviso('datos_desactualizados', t));
  return { avisos };
}

/** `true` si la última lectura correcta (ms epoch) es más antigua que el umbral o no existe. */
export function lecturaAntigua(
  ultimaLecturaOkMs: number | null,
  ahoraMs: number,
  umbralMs: number = UMBRAL_LECTURA_ANTIGUA_MS,
): boolean {
  if (ultimaLecturaOkMs === null) return true;
  return ahoraMs - ultimaLecturaOkMs > umbralMs;
}
