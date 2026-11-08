// Clasificación de errores de la API en motivos legibles. Sin Angular: acepta cualquier
// objeto con forma de `HttpErrorResponse` y nunca reenvía texto del cuerpo al usuario.
import { T_ES, Traductor } from '../i18n/traducir';

export type TipoError =
  | 'red'
  | 'parametro_invalido'
  | 'servicio_no_disponible'
  | 'error_interno'
  | 'respuesta_invalida'
  | 'http'
  | 'metodo_no_permitido'
  | 'configuracion'
  | 'desconocido';

export interface ErrorPanel {
  tipo: TipoError;
  /** Frase apta para mostrar tal cual. La app clasifica en español (también es la que van a los logs). */
  motivo: string;
  status: number | null;
  /** Nombre del parámetro rechazado (solo en `parametro_invalido`). */
  parametro: string | null;
}

const PARAMETRO_VALIDO = /^[a-z_]{1,40}$/;

/**
 * Motivo de un error ya clasificado en el idioma del traductor. Permite repintar un error guardado
 * al cambiar de idioma sin volver a pedirlo.
 */
export function motivoError(e: Pick<ErrorPanel, 'tipo' | 'status' | 'parametro'>, t: Traductor = T_ES): string {
  switch (e.tipo) {
    case 'metodo_no_permitido':
      return t('errores.metodo');
    case 'configuracion':
      return t('errores.configuracion');
    case 'respuesta_invalida':
      return t('errores.respuesta_invalida');
    case 'red':
      return t('errores.red');
    case 'parametro_invalido':
      return e.parametro
        ? t('errores.parametro', { parametro: e.parametro })
        : t('errores.parametro_generico');
    case 'servicio_no_disponible':
      return t('errores.servicio');
    case 'error_interno':
      return t('errores.interno');
    case 'http':
      return t('errores.http', { status: e.status ?? 0 });
    default:
      return t('errores.desconocido');
  }
}

function crear(
  tipo: TipoError,
  t: Traductor,
  status: number | null = null,
  parametro: string | null = null,
): ErrorPanel {
  return { tipo, motivo: motivoError({ tipo, status, parametro }, t), status, parametro };
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null;
}

export function clasificarError(error: unknown, t: Traductor = T_ES): ErrorPanel {
  if (!esObjeto(error)) return crear('desconocido', t);

  if (error['tipo'] === 'metodo_no_permitido') return crear('metodo_no_permitido', t);
  if (error['tipo'] === 'configuracion') return crear('configuracion', t);
  if (error['tipo'] === 'respuesta_invalida') return crear('respuesta_invalida', t, 200);

  const status = typeof error['status'] === 'number' ? error['status'] : null;
  if (status === null) return crear('desconocido', t);

  if (status === 0) return crear('red', t, 0);
  // HttpClient convierte un 200 con cuerpo que no es JSON en un error con status 200.
  if (status >= 200 && status < 300) return crear('respuesta_invalida', t, status);
  if (status === 400) {
    const cuerpo = esObjeto(error['error']) ? error['error'] : null;
    const crudo = cuerpo?.['parametro'];
    const parametro = typeof crudo === 'string' && PARAMETRO_VALIDO.test(crudo) ? crudo : null;
    return crear('parametro_invalido', t, 400, parametro);
  }
  if (status === 503) return crear('servicio_no_disponible', t, 503);
  if (status === 500) return crear('error_interno', t, 500);
  return crear('http', t, status);
}
