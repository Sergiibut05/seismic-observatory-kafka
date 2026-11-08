// Genera public/datos/paises-globo.geojson: fronteras simplificadas SOLO para dibujar el globo 3D.
// La asignación de país sigue usando el catálogo completo (public/datos/paises.geojson no se toca).
//
//   node scripts/fronteras-globo.mjs   → reescribe la copia simplificada a partir de la copia verificada
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const origen = resolve(raiz, 'public', 'datos', 'paises.geojson');
const destino = resolve(raiz, 'public', 'datos', 'paises-globo.geojson');
const TOLERANCIA = 0.12; // grados
const AREA_MIN = 0.05; // grados², descarta islotes que no se ven en el globo

function distanciaSegmento(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function douglasPeucker(puntos, TOLERANCIA) {
  const marcados = new Uint8Array(puntos.length);
  marcados[0] = marcados[puntos.length - 1] = 1;
  const pila = [[0, puntos.length - 1]];
  while (pila.length) {
    const [i, j] = pila.pop();
    let peor = -1;
    let indice = -1;
    for (let k = i + 1; k < j; k++) {
      const d = distanciaSegmento(puntos[k], puntos[i], puntos[j]);
      if (d > peor) [peor, indice] = [d, k];
    }
    if (peor > TOLERANCIA) {
      marcados[indice] = 1;
      pila.push([i, indice], [indice, j]);
    }
  }
  return puntos.filter((_, k) => marcados[k]);
}

const areaConSigno = (anillo) =>
  anillo.reduce((s, p, k) => s + (k ? anillo[k - 1][0] * p[1] - p[0] * anillo[k - 1][1] : 0), 0) / 2;
const area = (anillo) => Math.abs(areaConSigno(anillo));

const redondear = (p) => [Math.round(p[0] * 100) / 100, Math.round(p[1] * 100) / 100];

// El globo interpreta el sentido de giro: si un anillo se invierte al simplificar, el polígono pasa a ser
// «toda la esfera menos el país». Se reintenta con menos tolerancia y, en último caso, se deja el original.
function simplificar(anillo) {
  const original = areaConSigno(anillo);
  for (let tol = TOLERANCIA; tol > 0.005; tol /= 3) {
    const r = douglasPeucker(anillo, tol).map(redondear);
    const a = areaConSigno(r);
    if (r.length >= 4 && Math.sign(a) === Math.sign(original) && Math.abs(a - original) <= 0.15 * Math.abs(original)) {
      return r;
    }
  }
  return anillo;
}

function simplificarPoligono(anillos) {
  const [exterior, ...huecos] = anillos;
  if (area(exterior) < AREA_MIN) return null;
  const borde = simplificar(exterior);
  if (borde.length < 4) return null;
  const interiores = huecos
    .filter((h) => area(h) >= AREA_MIN)
    .map(simplificar)
    .filter((a) => a.length >= 4);
  return [borde, ...interiores];
}

const geo = JSON.parse(readFileSync(origen, 'utf8'));
let antes = 0;
let despues = 0;
const contar = (a) => (Array.isArray(a[0]) ? a.reduce((s, x) => s + contar(x), 0) : 1);
const features = [];
for (const f of geo.features) {
  const { type, coordinates } = f.geometry;
  antes += contar(coordinates);
  const poligonos = (type === 'Polygon' ? [coordinates] : coordinates).map(simplificarPoligono).filter(Boolean);
  if (!poligonos.length) continue;
  const coords = poligonos.length === 1 ? poligonos[0] : poligonos;
  despues += contar(coords);
  features.push({
    type: 'Feature',
    properties: { ADM0_A3: f.properties?.ADM0_A3 ?? null },
    geometry: { type: poligonos.length === 1 ? 'Polygon' : 'MultiPolygon', coordinates: coords },
  });
}
writeFileSync(destino, JSON.stringify({ type: 'FeatureCollection', features }));
console.log(
  `service=catalogo result=persistido destino=paises-globo.geojson paises=${features.length} vertices_antes=${antes} vertices_despues=${despues}`,
);
