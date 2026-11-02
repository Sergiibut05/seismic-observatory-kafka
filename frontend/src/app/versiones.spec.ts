import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

// `npm test` se ejecuta desde frontend/, así que las rutas son relativas a esa carpeta.
const leerJson = (ruta: string) => JSON.parse(readFileSync(ruta, 'utf8')) as Record<string, any>;

describe('dependencias fijadas (FR-017)', () => {
  const paquete = leerJson('package.json');

  it('ninguna dependencia usa ^ ni ~ ni rangos', () => {
    for (const bloque of ['dependencies', 'devDependencies'] as const) {
      for (const [nombre, version] of Object.entries(paquete[bloque] as Record<string, string>)) {
        expect(version, `${bloque}.${nombre}`).toMatch(/^\d+\.\d+\.\d+$/);
      }
    }
  });

  it('Leaflet y sus tipos están en las versiones del plan', () => {
    expect(paquete['dependencies']['leaflet']).toBe('1.9.4');
    expect(paquete['devDependencies']['@types/leaflet']).toBe('1.9.22');
  });

  it('el archivo de bloqueo existe y .npmrc exige versiones exactas', () => {
    expect(leerJson('package-lock.json')['lockfileVersion']).toBeGreaterThanOrEqual(3);
    expect(readFileSync('.npmrc', 'utf8')).toContain('save-exact=true');
  });
});

describe('catálogo de países (FR-002)', () => {
  it('la copia pública coincide con el SHA-256 del manifiesto', () => {
    const manifiesto = leerJson('../catalogo/paises.manifest.json');
    const copia = readFileSync('public/datos/paises.geojson');
    const hash = createHash('sha256').update(copia).digest('hex');
    expect(hash).toBe(manifiesto['output']['sha256']);
  });
});

describe('configuración (FR-012, FR-013)', () => {
  it('config.json solo contiene apiBaseUrl', () => {
    expect(Object.keys(leerJson('public/config.json'))).toEqual(['apiBaseUrl']);
    expect(Object.keys(leerJson('public/config.ejemplo.json'))).toEqual(['apiBaseUrl']);
  });
});
