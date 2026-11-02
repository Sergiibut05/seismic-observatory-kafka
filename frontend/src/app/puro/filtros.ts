// Filtros del panel: validación, serialización al contrato y acotado de la ventana horaria.
// Las fechas del formulario (`datetime-local`) se interpretan SIEMPRE como UTC.

export const SIN_PAIS = 'Sin país asignado';
export const MAX_VENTANA_HORA_MS = 31 * 24 * 3600 * 1000;

/** Lo que escribe la persona: texto tal cual de los campos. */
export interface FiltrosEditados {
  desde: string;
  hasta: string;
  magnitudMin: string;
  magnitudMax: string;
  pais: string;
  subregion: string;
}

export const FILTROS_VACIOS: FiltrosEditados = {
  desde: '',
  hasta: '',
  magnitudMin: '',
  magnitudMax: '',
  pais: '',
  subregion: '',
};

/** Filtros ya validados y normalizados; un campo ausente = sin filtro. */
export interface FiltrosAplicados {
  desde?: string;
  hasta?: string;
  magnitudMin?: number;
  magnitudMax?: number;
  pais?: string;
  subregion?: string;
}

export type CampoFiltro = keyof FiltrosEditados;
export type ErroresFiltros = Partial<Record<CampoFiltro, string>>;
export type ResultadoValidacion =
  | { ok: true; filtros: FiltrosAplicados }
  | { ok: false; errores: ErroresFiltros };

export type ModoQuery = 'completo' | 'comparacion' | 'hora';

const FECHA = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?Z?$/;
const NUMERO = /^-?\d{1,2}(?:[.,]\d{1,4})?$/;
const PAIS = /^[A-Z]{3}$/;

/** Devuelve el instante en ms epoch UTC o `null` si el texto no es una fecha real. */
function parsearInstante(texto: string): number | null {
  const m = FECHA.exec(texto);
  if (!m) return null;
  const [anio, mes, dia, hora, min, seg] = m.slice(1, 7).map((v) => Number(v ?? 0));
  const ms = Number((m[7] ?? '').padEnd(3, '0') || 0);
  const t = Date.UTC(anio, mes - 1, dia, hora, min, seg, ms);
  const f = new Date(t);
  const coincide =
    f.getUTCFullYear() === anio &&
    f.getUTCMonth() === mes - 1 &&
    f.getUTCDate() === dia &&
    f.getUTCHours() === hora &&
    f.getUTCMinutes() === min &&
    f.getUTCSeconds() === seg;
  return coincide ? t : null;
}

function parsearMagnitud(texto: string): number | null {
  if (!NUMERO.test(texto)) return null;
  const n = Number(texto.replace(',', '.'));
  return Number.isFinite(n) && n >= -10 && n <= 10 ? n : null;
}

export function validarFiltros(f: FiltrosEditados): ResultadoValidacion {
  const errores: ErroresFiltros = {};
  const filtros: FiltrosAplicados = {};
  const valor = (c: CampoFiltro) => f[c].trim();

  let desdeMs: number | null = null;
  let hastaMs: number | null = null;
  if (valor('desde')) {
    desdeMs = parsearInstante(valor('desde'));
    if (desdeMs === null) errores.desde = 'Fecha no válida (UTC, formato AAAA-MM-DDThh:mm).';
    else filtros.desde = new Date(desdeMs).toISOString();
  }
  if (valor('hasta')) {
    hastaMs = parsearInstante(valor('hasta'));
    if (hastaMs === null) errores.hasta = 'Fecha no válida (UTC, formato AAAA-MM-DDThh:mm).';
    else filtros.hasta = new Date(hastaMs).toISOString();
  }
  if (desdeMs !== null && hastaMs !== null && desdeMs >= hastaMs) {
    errores.hasta = 'La fecha final debe ser posterior a la inicial.';
  }

  let min: number | null = null;
  let max: number | null = null;
  if (valor('magnitudMin')) {
    min = parsearMagnitud(valor('magnitudMin'));
    if (min === null) errores.magnitudMin = 'Introduce un número entre −10 y 10.';
    else filtros.magnitudMin = min;
  }
  if (valor('magnitudMax')) {
    max = parsearMagnitud(valor('magnitudMax'));
    if (max === null) errores.magnitudMax = 'Introduce un número entre −10 y 10.';
    else filtros.magnitudMax = max;
  }
  if (min !== null && max !== null && min > max) {
    errores.magnitudMax = 'La magnitud máxima no puede ser menor que la mínima.';
  }

  const pais = valor('pais');
  if (pais) {
    if (pais === SIN_PAIS || PAIS.test(pais)) filtros.pais = pais;
    else errores.pais = 'Código de país no válido (tres letras mayúsculas).';
  }
  const subregion = valor('subregion');
  if (subregion) {
    if (subregion.length > 80) errores.subregion = 'Máximo 80 caracteres.';
    else filtros.subregion = subregion;
  }

  return Object.keys(errores).length ? { ok: false, errores } : { ok: true, filtros };
}

export interface VentanaAcotada {
  filtros: FiltrosAplicados;
  acotado: boolean;
}

/**
 * `/recuentos/hora` admite como máximo 31 días. Si el rango pedido lo supera, se usan los
 * últimos 31 días hasta `hasta` (o hasta ahora si solo hay `desde`). Sin `desde`, la API
 * usa 24 h y no hace falta acotar.
 */
export function acotarVentanaHora(f: FiltrosAplicados, ahoraMs: number): VentanaAcotada {
  if (!f.desde) return { filtros: f, acotado: false };
  const desde = Date.parse(f.desde);
  const hasta = f.hasta ? Date.parse(f.hasta) : ahoraMs;
  if (hasta - desde <= MAX_VENTANA_HORA_MS) return { filtros: f, acotado: false };
  return {
    filtros: {
      ...f,
      desde: new Date(hasta - MAX_VENTANA_HORA_MS).toISOString(),
      hasta: new Date(hasta).toISOString(),
    },
    acotado: true,
  };
}

/**
 * Serializa los filtros al contrato. Nunca emite `incluir_sinteticos`.
 * `extra` (p. ej. `limite`, `desplazamiento`) va al final.
 */
export function aQuery(
  filtros: FiltrosAplicados,
  modo: ModoQuery,
  extra: Record<string, string | number> = {},
  ahoraMs: number = Date.now(),
): string {
  const f = modo === 'hora' ? acotarVentanaHora(filtros, ahoraMs).filtros : filtros;
  const p = new URLSearchParams();
  if (modo !== 'comparacion') {
    if (f.desde) p.set('desde', f.desde);
    if (f.hasta) p.set('hasta', f.hasta);
  }
  if (f.magnitudMin !== undefined) p.set('magnitud_min', String(f.magnitudMin));
  if (f.magnitudMax !== undefined) p.set('magnitud_max', String(f.magnitudMax));
  if (f.pais) p.set('pais', f.pais);
  if (f.subregion) p.set('subregion', f.subregion);
  for (const [clave, valor] of Object.entries(extra)) p.set(clave, String(valor));
  return p.toString();
}
