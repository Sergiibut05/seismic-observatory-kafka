// Precarga del globo (011): todo lo que tarda y no depende de la pantalla se prepara antes de
// pasar del plano al globo, para que la escena se revele ya completa y no «salte» a medias.
//
//  · los módulos pesados (globe.gl y las mallas de columnas), que son un trozo aparte;
//  · las fronteras, que dibujan la Tierra;
//  · la textura de la Tierra de cada tema (4096 × 2048 a PNG: cientos de ms), que se guarda.
//
// Sin Angular. No se usa en jsdom (allí el globo está desactivado).
import type { PaletaMundo } from '../../puro/mundo';
import type { PaisGlobo } from '../../puro/globo';

export const URL_FRONTERAS = 'datos/paises-globo.geojson';
const ANCHO_TEXTURA = 4096;

export interface ModulosGlobo {
  Globe: typeof import('globe.gl').default;
  mallas: typeof import('./mallas');
  paises: PaisGlobo[];
}

let modulos: Promise<ModulosGlobo> | null = null;
const texturas = new Map<string, Promise<string | null>>();

export function soportaWebgl(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') ?? c.getContext('webgl'));
  } catch {
    return false;
  }
}

/** Módulos y fronteras, una sola vez. Si las fronteras fallan no se guarda: el siguiente intento las pide otra vez. */
export function precargarGlobo(): Promise<ModulosGlobo> {
  if (modulos) return modulos;
  let fallo = false;
  const intento = Promise.all([
    import('globe.gl'),
    import('./mallas'),
    cargarPaises(() => (fallo = true)),
  ]).then(([{ default: Globe }, mallas, paises]) => {
    if (fallo && modulos === intento) modulos = null;
    return { Globe, mallas, paises };
  });
  modulos = intento;
  intento.catch(() => {
    if (modulos === intento) modulos = null;
  });
  return intento;
}

async function cargarPaises(alFallar: () => void): Promise<PaisGlobo[]> {
  try {
    const r = await fetch(URL_FRONTERAS);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return ((await r.json()) as { features: PaisGlobo[] }).features;
  } catch (e) {
    alFallar();
    console.warn(
      `service=panel result=error bloque=globo-fronteras motivo="no se pudo cargar" detalle="${String(e)}"`,
    );
    return [];
  }
}

/** Textura de la Tierra con la paleta del tema: se dibuja una vez por paleta y se reutiliza (también al cambiar de tema). */
export function texturaTierra(
  paises: readonly PaisGlobo[],
  p: PaletaMundo,
): Promise<string | null> {
  const clave = `${p.oceano}|${p.tierra}|${p.frontera}`;
  let t = texturas.get(clave);
  if (!t) {
    t = dibujarTextura(paises, p).catch((e) => {
      texturas.delete(clave);
      console.warn(
        `service=panel result=error bloque=globo-textura motivo="no se pudo dibujar" detalle="${String(e)}"`,
      );
      return null;
    });
    texturas.set(clave, t);
  }
  return t;
}

/** Deja listo lo que el globo necesita para abrirse al instante con la paleta dada. */
export async function precalentarGlobo(p: PaletaMundo): Promise<void> {
  if (!soportaWebgl()) return;
  const { paises } = await precargarGlobo();
  if (paises.length) await texturaTierra(paises, p);
}

async function dibujarTextura(features: readonly PaisGlobo[], p: PaletaMundo): Promise<string> {
  const lienzo = document.createElement('canvas');
  lienzo.width = ANCHO_TEXTURA;
  lienzo.height = ANCHO_TEXTURA / 2;
  const ctx = lienzo.getContext('2d');
  if (!ctx) throw new Error('sin contexto 2d');
  const escala = ANCHO_TEXTURA / 360;
  ctx.fillStyle = p.oceano;
  ctx.fillRect(0, 0, lienzo.width, lienzo.height);

  const tierra = new Path2D();
  for (const f of features) {
    if (!f.geometry) continue;
    const poligonos = (
      f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates
    ) as number[][][][];
    for (const anillos of poligonos) {
      for (const anillo of anillos) {
        anillo.forEach(([lng, lat], k) => {
          const x = (lng + 180) * escala;
          const y = (90 - lat) * escala;
          if (k === 0) tierra.moveTo(x, y);
          else tierra.lineTo(x, y);
        });
        tierra.closePath();
      }
    }
  }
  ctx.fillStyle = p.tierra;
  ctx.fill(tierra, 'evenodd');
  ctx.strokeStyle = p.frontera;
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  ctx.stroke(tierra);

  const blob = await new Promise<Blob | null>((ok) => lienzo.toBlob(ok, 'image/png'));
  if (!blob) throw new Error('no se pudo codificar la textura');
  return URL.createObjectURL(blob);
}
