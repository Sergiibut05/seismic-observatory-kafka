import {
  altitudDesdeZoom,
  altitudParaAncho,
  normalizarLng,
  zoomDesdeAltitud,
  zoomParaAncho,
} from './mundo';

describe('mundo compartido', () => {
  it('normaliza longitudes de copias del mundo', () => {
    expect(normalizarLng(190)).toBe(-170);
    expect(normalizarLng(-190)).toBe(170);
    expect(normalizarLng(45)).toBe(45);
    expect(normalizarLng(Number.NaN)).toBe(0);
  });

  it('acerca la cámara al subir el zoom y respeta los límites', () => {
    expect(altitudDesdeZoom(4)).toBeLessThan(altitudDesdeZoom(2));
    expect(altitudDesdeZoom(18)).toBeGreaterThan(0);
    expect(altitudDesdeZoom(-5)).toBeLessThanOrEqual(2.6);
  });

  it('ida y vuelta plano → globo → plano conserva el zoom', () => {
    for (const z of [2, 3, 4.5, 6]) expect(zoomDesdeAltitud(altitudDesdeZoom(z))).toBe(z);
    expect(zoomDesdeAltitud(0)).toBe(2);
    expect(zoomDesdeAltitud(0.01)).toBe(8);
    expect(zoomDesdeAltitud(50)).toBe(1);
  });

  it('en vertical aleja la cámara para que el globo quepa a lo ancho', () => {
    expect(altitudParaAncho(1200, 700)).toBe(0);
    expect(altitudParaAncho(390, 560)).toBeGreaterThan(2);
    expect(altitudParaAncho(300, 700)).toBeGreaterThan(altitudParaAncho(390, 560));
  });

  it('elige el zoom inicial del plano según el ancho', () => {
    expect(zoomParaAncho(1050)).toBe(2);
    expect(zoomParaAncho(360)).toBe(1);
    expect(zoomParaAncho(0)).toBe(2);
  });
});
