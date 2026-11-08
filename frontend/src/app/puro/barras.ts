// Lógica pura de los gráficos de barras SVG (T7): escalas, tipo de barra, reparto de
// etiquetas y texto alternativo. Sin Angular. Un cero es una barra a cero (visible como línea);
// «sin valor» es otra categoría; un valor desconocido (`null`) es «ND» y no dibuja barra.
import { T_ES, Traductor } from '../i18n/traducir';
import { diaMesUtc, formatearEntero, textoNd } from './formato';

export type TipoBarra = 'normal' | 'cero' | 'sin-valor' | 'nd';

export interface DatoBarra {
  clave: string;
  etiqueta: string;
  /** Etiqueta breve del eje (por defecto, la completa). */
  etiquetaCorta?: string;
  /** `null` = desconocido (ND), nunca 0. */
  valor: number | null;
  /** Categoría «sin valor» (eventos sin magnitud/profundidad): se dibuja aparte y distinta. */
  sinValor?: boolean;
}

export interface BarraCalculada {
  clave: string;
  etiqueta: string;
  etiquetaCorta: string;
  valor: number | null;
  tipo: TipoBarra;
  /** Longitud relativa 0..1 respecto del máximo de la escala (0 para cero, sin valor y ND). */
  fraccion: number;
  valorTexto: string;
}

/** Máximo «redondo» (1, 2, 2,5, 5 × 10^k) que contiene a todos los valores; mínimo 1. */
export function escalaMaxima(valores: ReadonlyArray<number | null>): number {
  const m = Math.max(0, ...valores.filter((v): v is number => typeof v === 'number' && Number.isFinite(v)));
  if (m <= 1) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(m)));
  for (const paso of [1, 2, 2.5, 5, 10]) {
    if (m <= paso * exp) return paso * exp;
  }
  return 10 * exp;
}

/** Marcas enteras del eje de valores: `0, max/n, …, max` con 2 a 5 tramos si el máximo lo permite. */
export function marcasEscala(max: number): number[] {
  if (!(max > 0)) return [0];
  const n = [4, 5, 2, 3, 1].find((k) => Number.isInteger(max / k)) ?? 1;
  return Array.from({ length: n + 1 }, (_, i) => (max / n) * i);
}

export function tipoDeBarra(d: DatoBarra): TipoBarra {
  if (d.valor === null || d.valor === undefined || !Number.isFinite(d.valor)) return 'nd';
  if (d.sinValor) return 'sin-valor';
  return d.valor === 0 ? 'cero' : 'normal';
}

export function calcularBarras(datos: ReadonlyArray<DatoBarra>, max: number, t: Traductor = T_ES): BarraCalculada[] {
  return datos.map((d) => {
    const tipo = tipoDeBarra(d);
    const conLongitud = tipo === 'normal' && max > 0;
    return {
      clave: d.clave,
      etiqueta: d.etiqueta,
      etiquetaCorta: d.etiquetaCorta ?? d.etiqueta,
      valor: tipo === 'nd' ? null : d.valor,
      tipo,
      fraccion: conLongitud ? Math.min(1, (d.valor as number) / max) : 0,
      valorTexto: tipo === 'nd' ? textoNd(t) : formatearEntero(d.valor, t),
    };
  });
}

/** Índices de las etiquetas que caben: reparto uniforme, siempre el primero y el último si caben. */
export function indicesEtiquetasVisibles(n: number, maxEtiquetas: number): number[] {
  if (n <= 0) return [];
  if (maxEtiquetas >= n) return Array.from({ length: n }, (_, i) => i);
  if (maxEtiquetas <= 1) return [0];
  const paso = Math.ceil(n / maxEtiquetas);
  const idx: number[] = [];
  for (let i = 0; i < n; i += paso) idx.push(i);
  return idx;
}

export function acortar(texto: string, maxCaracteres: number): string {
  return texto.length <= maxCaracteres ? texto : `${texto.slice(0, Math.max(1, maxCaracteres - 1))}…`;
}

/** `16:00` a partir de un instante ISO UTC (`ND` si no es válido). */
export function etiquetaHoraUtc(iso: string, t: Traductor = T_ES): string {
  const f = new Date(iso);
  if (Number.isNaN(f.getTime())) return textoNd(t);
  return `${String(f.getUTCHours()).padStart(2, '0')}:00`;
}

/** `01/11 16:00 UTC` en español, `1 Nov 16:00 UTC` en inglés. */
export function etiquetaVentanaUtc(iso: string, t: Traductor = T_ES): string {
  const f = new Date(iso);
  if (Number.isNaN(f.getTime())) return textoNd(t);
  return `${diaMesUtc(f, t)} ${etiquetaHoraUtc(iso, t)} UTC`;
}

/** Texto para `aria-label`: título, total, mayor categoría y cuántas están a cero / sin valor / ND. */
export function textoAlternativo(
  titulo: string,
  barras: ReadonlyArray<BarraCalculada>,
  unidad: string,
  t: Traductor = T_ES,
): string {
  if (barras.length === 0) return t('grafico.alt_vacio', { titulo });
  const conValor = barras.filter((b) => b.valor !== null);
  const total = conValor.reduce((s, b) => s + (b.valor as number), 0);
  const partes = [
    `${titulo}.`,
    t('grafico.alt_resumen', { n: barras.length, total: formatearEntero(total, t), unidad }),
  ];
  const mayor = conValor
    .filter((b) => b.tipo === 'normal')
    .reduce<BarraCalculada | null>((a, b) => (a === null || (b.valor as number) > (a.valor as number) ? b : a), null);
  if (mayor) partes.push(t('grafico.alt_mayor', { etiqueta: mayor.etiqueta, valor: mayor.valorTexto }));
  const ceros = barras.filter((b) => b.tipo === 'cero').length;
  if (ceros > 0) partes.push(t('grafico.alt_ceros', { n: ceros }));
  const sin = barras.find((b) => b.tipo === 'sin-valor');
  if (sin) partes.push(t('grafico.alt_sin_valor', { valor: sin.valorTexto }));
  const nd = barras.filter((b) => b.tipo === 'nd').length;
  if (nd > 0) partes.push(t('grafico.alt_nd', { n: nd }));
  partes.push(t('grafico.alt_tabla'));
  return partes.join(' ');
}

/**
 * Las `max` mayores categorías (en el orden recibido), más una barra «Resto» con la suma de las
 * demás. Las categorías de `obligatorias` (p. ej. «Sin país asignado») se mantienen siempre.
 */
export function principalesConResto(
  datos: ReadonlyArray<DatoBarra>,
  max: number,
  obligatorias: ReadonlyArray<string> = [],
  etiquetaResto = 'Resto',
): DatoBarra[] {
  if (datos.length <= max) return [...datos];
  const ordenadas = [...datos].sort((a, b) => (b.valor ?? -1) - (a.valor ?? -1));
  const fijas = ordenadas.filter((d) => obligatorias.includes(d.etiqueta));
  const libres = ordenadas.filter((d) => !obligatorias.includes(d.etiqueta));
  const hueco = Math.max(0, max - fijas.length);
  const visibles = new Set([...fijas, ...libres.slice(0, hueco)]);
  const resto = ordenadas.filter((d) => !visibles.has(d));
  const salida = ordenadas.filter((d) => visibles.has(d));
  if (resto.length > 0) {
    salida.push({
      clave: '__resto',
      etiqueta: `${etiquetaResto} (${resto.length})`,
      valor: resto.reduce((s, d) => s + (d.valor ?? 0), 0),
    });
  }
  return salida;
}
