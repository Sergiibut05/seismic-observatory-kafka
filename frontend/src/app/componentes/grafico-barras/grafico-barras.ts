import {
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { I18nService } from '../../i18n/i18n.service';
import { Clave } from '../../i18n/es';
import {
  BarraCalculada,
  DatoBarra,
  TipoBarra,
  acortar,
  calcularBarras,
  escalaMaxima,
  indicesEtiquetasVisibles,
  marcasEscala,
  textoAlternativo,
} from '../../puro/barras';
import { formatearEntero, formatearPorcentaje } from '../../puro/formato';

export type Orientacion = 'horizontal' | 'vertical';

/** Línea de referencia de una gráfica vertical (p. ej. la media por hora). */
export interface Referencia {
  valor: number;
  etiqueta: string;
}

interface ElementoBarra {
  clave: string;
  tipo: TipoBarra;
  etiqueta: string;
  /** Rectángulo (nulo en «ND»). */
  x: number;
  y: number;
  ancho: number;
  alto: number;
  /** Posición del valor. */
  vx: number;
  vy: number;
  vAncla: 'start' | 'middle' | 'end';
  valorTexto: string;
  /** Etiqueta de categoría en el eje (nula si no cabe). */
  ex: number;
  ey: number;
  eAncla: 'start' | 'middle' | 'end';
  etiquetaEje: string | null;
  /** Barra con el extremo libre redondeado y la base recta. */
  d: string;
  /** Zona de puntería (más grande que la barra). */
  hx: number;
  hy: number;
  hw: number;
  hh: number;
  /** Ancla del tooltip, en píxeles del lienzo. */
  tx: number;
  ty: number;
  esMax: boolean;
  /** Parte del total («74,2 %»), o nulo si la gráfica no reparte un total. */
  cuota: string | null;
  /** Muestra de color bajo el eje (p. ej. el color de esa profundidad en el mapa). */
  color: string | null;
}

interface Marca {
  texto: string;
  /** Posición de la línea guía (y). */
  pos: number;
}

const RADIO_EXTREMO = 4;
/** Ancho del lienzo mientras no se ha medido el contenedor (y en los tests, sin `ResizeObserver`). */
const ANCHO_INICIAL: Record<Orientacion, number> = { horizontal: 560, vertical: 560 };
const r1 = (n: number) => Math.round(n * 10) / 10;

/** Rectángulo con el extremo libre redondeado (arriba en vertical, a la derecha en horizontal). */
export function caminoBarra(
  x: number,
  y: number,
  w: number,
  h: number,
  horizontal: boolean,
): string {
  if (w <= 0 || h <= 0) return '';
  if (horizontal) {
    const r = Math.min(RADIO_EXTREMO, h / 2, w);
    return `M${r1(x)} ${r1(y)}H${r1(x + w - r)}Q${r1(x + w)} ${r1(y)} ${r1(x + w)} ${r1(y + r)}V${r1(y + h - r)}Q${r1(x + w)} ${r1(y + h)} ${r1(x + w - r)} ${r1(y + h)}H${r1(x)}Z`;
  }
  const r = Math.min(RADIO_EXTREMO, w / 2, h);
  return `M${r1(x)} ${r1(y + h)}V${r1(y + r)}Q${r1(x)} ${r1(y)} ${r1(x + r)} ${r1(y)}H${r1(x + w - r)}Q${r1(x + w)} ${r1(y)} ${r1(x + w)} ${r1(y + r)}V${r1(y + h)}Z`;
}

const OBSERVACION: Record<TipoBarra, Clave | null> = {
  normal: null,
  cero: 'grafico.obs_cero',
  'sin-valor': 'grafico.obs_sin_valor',
  nd: 'grafico.obs_nd',
};

let contador = 0;

/**
 * Gráfico de barras en SVG propio (sin librería). El lienzo mide lo mismo que su contenedor, así
 * que una unidad es un píxel y el texto no se encoge. `role="img"` con un `aria-label`
 * descriptivo y una tabla equivalente en un `<details>`; el cero se dibuja como línea con borde,
 * «sin valor» como barra rayada aparte y «ND» solo como texto: no depende solo del color.
 */
@Component({
  selector: 'app-grafico-barras',
  templateUrl: './grafico-barras.html',
  styleUrl: './grafico-barras.css',
})
export class GraficoBarras {
  readonly titulo = input.required<string>();
  readonly datos = input.required<DatoBarra[]>();
  readonly orientacion = input<Orientacion>('horizontal');
  /** Qué cuentan las barras (p. ej. «eventos»). */
  readonly unidad = input<string>('eventos');
  /** Texto del eje de categorías (p. ej. «Hora UTC»). Solo en vertical. */
  readonly ejeTitulo = input<string>('');
  /** Filas de la tabla equivalente si difieren de las barras (p. ej. todos los países). */
  readonly filasTabla = input<DatoBarra[] | null>(null);
  /** Las barras reparten un total: se muestra qué parte es cada una. */
  readonly cuota = input(false);
  /** Línea de referencia (solo en vertical). */
  readonly referencia = input<Referencia | null>(null);
  /** Alto de la zona de barras en vertical, en píxeles. */
  readonly alto = input(168);

  protected readonly i18n = inject(I18nService);
  protected readonly idPatron = `rayas-${++contador}`;
  /** Barra bajo el puntero: realce y tooltip. */
  protected readonly activo = signal<number | null>(null);
  private readonly lienzo = viewChild<ElementRef<HTMLElement>>('lienzo');
  private readonly anchoMedido = signal<number | null>(null);

  constructor() {
    const destruir = inject(DestroyRef);
    afterNextRender(() => {
      const el = this.lienzo()?.nativeElement;
      if (!el || typeof ResizeObserver === 'undefined') return;
      const observador = new ResizeObserver((entradas) => {
        const ancho = Math.round(entradas[0]?.contentRect.width ?? 0);
        if (ancho > 0) this.anchoMedido.set(ancho);
      });
      observador.observe(el);
      destruir.onDestroy(() => observador.disconnect());
    });
  }

  protected readonly tip = computed(() => {
    const i = this.activo();
    const g = this.geometria();
    const e = i === null ? undefined : g.elementos[i];
    if (!e) return null;
    // El tooltip no se sale del lienzo: se ancla al borde que tenga más cerca.
    const lado: 'centro' | 'izquierda' | 'derecha' =
      e.tx < 96 ? 'izquierda' : e.tx > g.W - 96 ? 'derecha' : 'centro';
    return { etiqueta: e.etiqueta, valor: e.valorTexto, cuota: e.cuota, x: e.tx, y: e.ty, lado };
  });

  protected readonly barras = computed<BarraCalculada[]>(() => {
    const datos = this.datos();
    return calcularBarras(datos, escalaMaxima(datos.map((d) => d.valor)), this.i18n.t());
  });
  protected readonly filas = computed<BarraCalculada[]>(() => {
    const f = this.filasTabla();
    if (f === null) return this.barras();
    return calcularBarras(f, escalaMaxima(f.map((d) => d.valor)), this.i18n.t());
  });
  protected readonly textoAlt = computed(() =>
    textoAlternativo(this.titulo(), this.barras(), this.unidad(), this.i18n.t()),
  );
  protected readonly tiposPresentes = computed(() => new Set(this.barras().map((b) => b.tipo)));

  protected readonly geometria = computed(() =>
    this.orientacion() === 'horizontal' ? this.horizontal() : this.vertical(),
  );

  protected observacion(t: TipoBarra): string {
    const clave = OBSERVACION[t];
    return clave === null ? '' : this.i18n.tr(clave);
  }

  /** Suma de todo lo que tiene valor: el 100 % de las cuotas. */
  private total(): number {
    return this.datos().reduce(
      (s, d) => s + (typeof d.valor === 'number' && Number.isFinite(d.valor) ? d.valor : 0),
      0,
    );
  }

  private cuotaDe(b: BarraCalculada, total: number): string | null {
    if (!this.cuota() || b.valor === null || total <= 0) return null;
    return formatearPorcentaje((b.valor / total) * 100, this.i18n.t());
  }

  /** Lista ordenada: categoría, barra desde un mismo origen, valor en la punta y cuota a la derecha. */
  private horizontal() {
    const barras = this.barras();
    const total = this.total();
    const conCuota = this.cuota() && total > 0;
    const maxValor = Math.max(
      1,
      ...barras.map((b) => (b.tipo === 'normal' ? (b.valor as number) : 0)),
    );
    const W = this.anchoMedido() ?? ANCHO_INICIAL.horizontal;
    const mI = Math.round(Math.min(184, Math.max(88, W * 0.3)));
    const mD = conCuota ? 104 : 52;
    const mS = 4;
    const fila = 26;
    const grosor = 10;
    const hueco = 10; // separación antes de la categoría «sin valor»
    const ancho = Math.max(24, W - mI - mD);
    const maxCaracteres = Math.max(8, Math.floor((mI - 12) / 6.4));
    let y = mS;
    const elementos: ElementoBarra[] = barras.map((b) => {
      if (b.tipo === 'sin-valor') y += hueco;
      const yBarra = y + (fila - grosor) / 2;
      const largo =
        b.tipo === 'cero' || b.tipo === 'sin-valor'
          ? 4
          : b.tipo === 'normal'
            ? Math.max(((b.valor as number) / maxValor) * ancho, 2)
            : 0;
      const yFila = y;
      y += fila;
      return {
        clave: b.clave,
        tipo: b.tipo,
        etiqueta: b.etiqueta,
        x: mI,
        y: yBarra,
        ancho: largo,
        alto: grosor,
        vx: mI + largo + 8,
        vy: yBarra + grosor / 2,
        vAncla: 'start',
        valorTexto: b.valorTexto,
        ex: mI - 12,
        ey: yBarra + grosor / 2,
        eAncla: 'end',
        etiquetaEje: acortar(b.etiquetaCorta, maxCaracteres),
        d: b.tipo === 'normal' ? caminoBarra(mI, yBarra, largo, grosor, true) : '',
        hx: 0,
        hy: yFila,
        hw: W,
        hh: fila,
        tx: mI + largo / 2,
        ty: yFila,
        esMax: b.tipo === 'normal' && b.valor === maxValor,
        cuota: this.cuotaDe(b, total),
        color: null,
      };
    });
    return {
      W,
      H: y + mS,
      elementos,
      marcas: [] as Marca[],
      ejeBase: y,
      mI,
      mS,
      plotAncho: ancho,
      fuente: 12,
      separador: null as number | null,
      referencia: null as { y: number; etiqueta: string } | null,
      conColor: false,
      xCuota: W - 2,
    };
  }

  private vertical() {
    const barras = this.barras();
    const total = this.total();
    const maxFraccion = Math.max(
      0,
      ...barras.filter((b) => b.tipo === 'normal').map((b) => b.fraccion),
    );
    const max = escalaMaxima(this.datos().map((d) => d.valor));
    const t = this.i18n.t();
    const W = this.anchoMedido() ?? ANCHO_INICIAL.vertical;
    const marcasValor = marcasEscala(max);
    const mI = 14 + Math.max(...marcasValor.map((m) => formatearEntero(m, t).length)) * 6.6;
    const ref = this.referencia();
    // La etiqueta de la referencia va fuera de las barras, en el margen derecho.
    const mD = ref ? 14 + ref.etiqueta.length * 6.2 : 8;
    const mS = 24;
    const plotAlto = this.alto();
    const ancho = Math.max(24, W - mI - mD);
    const haySinValor = barras.some((b) => b.tipo === 'sin-valor');
    const extra = haySinValor ? 0.6 : 0;
    const ranura = ancho / Math.max(barras.length + extra, 1);
    const grosor = Math.max(3, Math.min(ranura - 2, ranura * 0.68, 24));
    const visibles = new Set(
      indicesEtiquetasVisibles(barras.length, Math.max(1, Math.floor(ancho / 52))),
    );
    const conColor = this.datos().some((d) => !!d.color);
    const base = mS + plotAlto;
    const yEtiqueta = base + (conColor ? 30 : 18);
    let desplazar = 0;
    const elementos: ElementoBarra[] = barras.map((b, i) => {
      if (b.tipo === 'sin-valor') desplazar = extra;
      const cx = mI + (i + desplazar + 0.5) * ranura;
      const altoBarra =
        b.tipo === 'cero' || b.tipo === 'sin-valor'
          ? 4
          : b.tipo === 'normal'
            ? Math.max(b.fraccion * plotAlto, 2)
            : 0;
      return {
        clave: b.clave,
        tipo: b.tipo,
        etiqueta: b.etiqueta,
        x: cx - grosor / 2,
        y: base - altoBarra,
        ancho: grosor,
        alto: altoBarra,
        vx: cx,
        vy: base - altoBarra - 6,
        vAncla: 'middle',
        valorTexto: b.valorTexto,
        ex: cx,
        ey: yEtiqueta,
        eAncla: 'middle',
        etiquetaEje:
          b.tipo === 'sin-valor'
            ? b.etiquetaCorta
            : visibles.has(i)
              ? acortar(b.etiquetaCorta, Math.max(5, Math.floor(Math.max(ranura, 52) / 6.2)))
              : null,
        d:
          b.tipo === 'normal'
            ? caminoBarra(cx - grosor / 2, base - altoBarra, grosor, altoBarra, false)
            : '',
        hx: cx - ranura / 2,
        hy: mS - 8,
        hw: ranura,
        hh: plotAlto + 8 + (conColor ? 36 : 24),
        tx: cx,
        ty: base - altoBarra,
        esMax: b.tipo === 'normal' && b.fraccion === maxFraccion,
        cuota: this.cuotaDe(b, total),
        color: this.datos()[i]?.color ?? null,
      };
    });
    const marcas: Marca[] = marcasValor.map((m) => ({
      texto: formatearEntero(m, t),
      pos: base - (m / max) * plotAlto,
    }));
    const referencia =
      ref && ref.valor > 0 && ref.valor <= max
        ? { y: base - (ref.valor / max) * plotAlto, etiqueta: ref.etiqueta }
        : null;
    return {
      W,
      H: yEtiqueta + (this.ejeTitulo() ? 30 : 8),
      elementos,
      marcas,
      ejeBase: base,
      mI,
      mS,
      plotAncho: ancho,
      fuente: 12,
      separador: haySinValor
        ? mI + (barras.findIndex((b) => b.tipo === 'sin-valor') + extra / 2) * ranura
        : null,
      referencia,
      conColor,
      xCuota: W,
    };
  }
}
