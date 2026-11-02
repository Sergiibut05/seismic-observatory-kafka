// Cuándo avisar de que los datos no son frescos. Sin Angular.
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

const TEXTOS: Record<CodigoAviso, string> = {
  api_sin_respuesta: 'La API no responde: se muestran los últimos datos recibidos.',
  base_fallida: 'La base de datos no responde: las cifras no están disponibles.',
  datos_desactualizados: 'Los datos están desactualizados: la última ingesta de USGS es antigua.',
};

const aviso = (codigo: CodigoAviso): Aviso => ({ codigo, texto: TEXTOS[codigo] });

/**
 * Deriva los avisos del estado del sistema (FR-008).
 * @param ultimo  última respuesta correcta de `/status` (o `null` si no hubo ninguna)
 * @param fallo   `true` si la última consulta de `/status` falló
 */
export function calcularEstado(ultimo: EstadoApi | null, fallo: boolean): ResultadoEstado {
  // Con la API caída no sabemos nada actual: un único aviso, sin mezclar lecturas viejas.
  if (fallo) return { avisos: [aviso('api_sin_respuesta')] };
  if (!ultimo) return { avisos: [] };
  const avisos: Aviso[] = [];
  if (ultimo.base_de_datos === 'fallida') avisos.push(aviso('base_fallida'));
  if (ultimo.datos_desactualizados === true) avisos.push(aviso('datos_desactualizados'));
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
