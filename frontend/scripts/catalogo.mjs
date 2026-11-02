// Copia y verifica el catálogo de países que usa el mapa.
//
// Fuente única de verdad: ../catalogo/paises.geojson (se genera con los scripts del repo).
// La copia public/datos/paises.geojson NO se edita a mano: este script la sobrescribe.
//
//   node scripts/catalogo.mjs copiar     → copia el origen sobre public/datos/paises.geojson
//   node scripts/catalogo.mjs verificar  → compara el SHA-256 de la copia con el del manifiesto
//
// Si la verificación falla, restaura la copia con `npm run catalogo:copiar`.
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const origen = resolve(raiz, '..', 'catalogo', 'paises.geojson');
const manifiesto = resolve(raiz, '..', 'catalogo', 'paises.manifest.json');
const copia = resolve(raiz, 'public', 'datos', 'paises.geojson');

const sha256 = (ruta) => createHash('sha256').update(readFileSync(ruta)).digest('hex');

function fallar(mensaje) {
  console.error(`service=catalogo result=error ${mensaje}`);
  process.exit(1);
}

function copiar() {
  if (!existsSync(origen)) fallar(`motivo="no existe el origen" ruta=${origen}`);
  mkdirSync(dirname(copia), { recursive: true });
  copyFileSync(origen, copia);
  console.log(`service=catalogo result=persistido sha256=${sha256(copia)}`);
}

function verificar() {
  if (!existsSync(copia)) fallar('motivo="falta la copia; ejecuta npm run catalogo:copiar"');
  const obtenido = sha256(copia);
  // En Netlify no existe ../catalogo: allí la copia versionada y su hash son lo único disponible.
  if (!existsSync(manifiesto)) {
    fallar(`motivo="falta catalogo/paises.manifest.json" sha256=${obtenido}`);
  }
  const esperado = JSON.parse(readFileSync(manifiesto, 'utf8'))?.output?.sha256;
  if (obtenido !== esperado) {
    fallar(
      `motivo="la copia no coincide con el manifiesto; ejecuta npm run catalogo:copiar" esperado=${esperado} obtenido=${obtenido}`,
    );
  }
  if (existsSync(origen) && sha256(origen) !== esperado) {
    fallar('motivo="el origen no coincide con el manifiesto"');
  }
  console.log(`service=catalogo result=omitido motivo="copia verificada" sha256=${obtenido}`);
}

const acciones = { copiar, verificar };
const accion = acciones[process.argv[2]];
if (!accion) fallar('motivo="uso: catalogo.mjs copiar|verificar"');
accion();
