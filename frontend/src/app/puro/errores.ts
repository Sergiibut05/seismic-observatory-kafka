// Clasificación de errores de la API en motivos legibles. Sin Angular: acepta cualquier
// objeto con forma de `HttpErrorResponse` y nunca reenvía texto del cuerpo al usuario.

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
  /** Frase en español, apta para mostrar tal cual. */
  motivo: string;
  status: number | null;
  /** Nombre del parámetro rechazado (solo en `parametro_invalido`). */
  parametro: string | null;
}

const PARAMETRO_VALIDO = /^[a-z_]{1,40}$/;

function crear(tipo: TipoError, motivo: string, status: number | null = null, parametro: string | null = null): ErrorPanel {
  return { tipo, motivo, status, parametro };
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null;
}

export function clasificarError(error: unknown): ErrorPanel {
  if (!esObjeto(error)) return crear('desconocido', 'Error inesperado en el panel.');

  if (error['tipo'] === 'metodo_no_permitido') {
    return crear('metodo_no_permitido', 'El panel solo realiza peticiones GET.');
  }
  if (error['tipo'] === 'configuracion') {
    return crear('configuracion', 'La configuración de la API no es válida.');
  }

  if (error['tipo'] === 'respuesta_invalida') {
    return crear(
      'respuesta_invalida',
      'La API devolvió una respuesta que no es JSON (¿página de aviso de ngrok?).',
      200,
    );
  }

  const status = typeof error['status'] === 'number' ? error['status'] : null;
  if (status === null) return crear('desconocido', 'Error inesperado en el panel.');

  if (status === 0) {
    return crear(
      'red',
      'La API no responde (red, túnel de ngrok caído o bloqueo CORS).',
      0,
    );
  }
  // HttpClient convierte un 200 con cuerpo que no es JSON en un error con status 200.
  if (status >= 200 && status < 300) {
    return crear(
      'respuesta_invalida',
      'La API devolvió una respuesta que no es JSON (¿página de aviso de ngrok?).',
      status,
    );
  }
  if (status === 400) {
    const cuerpo = esObjeto(error['error']) ? error['error'] : null;
    const crudo = cuerpo?.['parametro'];
    const parametro = typeof crudo === 'string' && PARAMETRO_VALIDO.test(crudo) ? crudo : null;
    const motivo = parametro
      ? `La API rechazó el parámetro «${parametro}».`
      : 'La API rechazó la consulta por un parámetro no válido.';
    return crear('parametro_invalido', motivo, 400, parametro);
  }
  if (status === 503) {
    return crear(
      'servicio_no_disponible',
      'Servicio no disponible: la base de datos no responde.',
      503,
    );
  }
  if (status === 500) {
    return crear('error_interno', 'Error interno de la API.', 500);
  }
  return crear('http', `La API respondió con el estado HTTP ${status}.`, status);
}
