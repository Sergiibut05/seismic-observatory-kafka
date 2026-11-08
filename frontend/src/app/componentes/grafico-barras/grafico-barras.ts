import { Component, computed, inject, input } from '@angular/core';
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
import { formatearEntero } from '../../puro/formato';

export type Orientacion = 'horizontal' | 'vertical';

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
  tooltip: string;
}

interface Marca {
  texto: string;
  /** Posición de la línea guía: x en horizontal, y en vertical. */
  pos: number;
}

const OBSERVACION: Record<TipoBarra, Clave | null> = {
  normal: null,
  cero: 'grafico.obs_cero',
  'sin-valor': 'grafico.obs_sin_valor',
  nd: 'grafico.obs_nd',
};

let contador = 0;

/**
 * Gráfico de barras en SVG propio (sin librería). Tiene `role="img"` con un `aria-label` descriptivo
 * y una tabla equivalente en un `<details>`; el cero se dibuja como línea con borde, «sin valor»
 * como barra rayada aparte y «ND» solo como texto: no depende solo del color.
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
  /** Texto del eje de categorías (p. ej. «Hora UTC»). */
  readonly ejeTitulo = input<string>('');
  /** Filas de la tabla equivalente si difieren de las barras (p. ej. todos los países). */
  readonly filasTabla = input<DatoBarra[] | null>(null);

  protected readonly i18n = inject(I18nService);
  protected readonly idPatron = `rayas-${++contador}`;

  protected readonly barras = computed<BarraCalculada[]>(() => {
    const datos = this.datos();
    return calcularBarras(datos, escalaMaxima(datos.map((d) => d.valor)), this.i18n.t());
  });
  protected readonly maximo = computed(() => escalaMaxima(this.datos().map((d) => d.valor)));
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

  private horizontal() {
    const barras = this.barras();
    const max = this.maximo();
    const W = 640;
    const mI = 168;
    const mD = 56;
    const mS = 8;
    const fila = 26;
    const grosor = 16;
    const hueco = 10; // separación antes de la categoría «sin valor»
    const ancho = W - mI - mD;
    let y = mS;
    const elementos: ElementoBarra[] = barras.map((b) => {
      if (b.tipo === 'sin-valor') y += hueco;
      const alto = grosor;
      const yBarra = y + (fila - grosor) / 2;
      const largo = b.tipo === 'cero' || b.tipo === 'sin-valor' ? 4 : Math.max(b.fraccion * ancho, b.tipo === 'normal' ? 2 : 0);
      y += fila;
      return {
        clave: b.clave,
        tipo: b.tipo,
        etiqueta: b.etiqueta,
        x: mI,
        y: yBarra,
        ancho: b.tipo === 'nd' ? 0 : largo,
        alto,
        vx: mI + (b.tipo === 'nd' ? 0 : largo) + 6,
        vy: yBarra + alto / 2,
        vAncla: 'start',
        valorTexto: b.valorTexto,
        ex: mI - 8,
        ey: yBarra + alto / 2,
        eAncla: 'end',
        etiquetaEje: acortar(b.etiquetaCorta, 24),
        tooltip: `${b.etiqueta}: ${b.valorTexto}`,
      };
    });
    const marcas: Marca[] = marcasEscala(max).map((m) => ({
      texto: formatearEntero(m, this.i18n.t()),
      pos: mI + (m / max) * ancho,
    }));
    const alto = y + 44;
    return {
      W,
      H: alto,
      elementos,
      marcas,
      ejeBase: y,
      mI,
      mD,
      mS,
      plotAncho: ancho,
      plotAlto: y - mS,
      fuente: 11,
      separador: null as number | null,
    };
  }

  private vertical() {
    const barras = this.barras();
    const max = this.maximo();
    const W = 720;
    const mI = 46;
    const mD = 10;
    const mS = 22;
    const plotAlto = 170;
    const ancho = W - mI - mD;
    const haySinValor = barras.some((b) => b.tipo === 'sin-valor');
    const extra = haySinValor ? 0.7 : 0;
    const ranuras = barras.length + extra;
    const ranura = ancho / Math.max(ranuras, 1);
    const grosor = Math.min(ranura * 0.7, 56);
    const visibles = new Set(indicesEtiquetasVisibles(barras.length, Math.max(1, Math.floor(ancho / 48))));
    const fuente = ranura < 18 ? 9 : 11;
    let desplazar = 0;
    const elementos: ElementoBarra[] = barras.map((b, i) => {
      if (b.tipo === 'sin-valor') desplazar = extra;
      const cx = mI + (i + desplazar + 0.5) * ranura;
      const base = mS + plotAlto;
      const altoBarra =
        b.tipo === 'cero' || b.tipo === 'sin-valor' ? 4 : b.tipo === 'normal' ? Math.max(b.fraccion * plotAlto, 2) : 0;
      return {
        clave: b.clave,
        tipo: b.tipo,
        etiqueta: b.etiqueta,
        x: cx - grosor / 2,
        y: base - altoBarra,
        ancho: grosor,
        alto: altoBarra,
        vx: cx,
        vy: base - altoBarra - 4,
        vAncla: 'middle',
        valorTexto: b.valorTexto,
        ex: cx,
        ey: base + 16,
        eAncla: 'middle',
        etiquetaEje: visibles.has(i) || b.tipo === 'sin-valor' ? acortar(b.etiquetaCorta, ranura > 40 ? 9 : 6) : null,
        tooltip: `${b.etiqueta}: ${b.valorTexto}`,
      };
    });
    const marcas: Marca[] = marcasEscala(max).map((m) => ({
      texto: formatearEntero(m, this.i18n.t()),
      pos: mS + plotAlto - (m / max) * plotAlto,
    }));
    return {
      W,
      H: mS + plotAlto + (this.ejeTitulo() ? 46 : 28),
      elementos,
      marcas,
      ejeBase: mS + plotAlto,
      mI,
      mD,
      mS,
      plotAncho: ancho,
      plotAlto,
      fuente,
      separador: haySinValor ? mI + (barras.findIndex((b) => b.tipo === 'sin-valor') + 0.35) * ranura : null,
    };
  }
}
