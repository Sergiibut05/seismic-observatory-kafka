import { TestBed } from '@angular/core/testing';
import { crearFicha, crearResumen } from '../componentes/mapa/mapa-ficha';
import { PropiedadesEventoMapa } from '../modelos/api';
import { textoAviso } from '../puro/desactualizado';
import { clasificarError } from '../puro/errores';
import { notaOrigenDatos, validarFiltros, FILTROS_VACIOS } from '../puro/filtros';
import { etiquetaVentanaUtc } from '../puro/barras';
import { formatearDecimal, formatearInstanteUtc, formatearMagnitud, formatearProfundidad } from '../puro/formato';
import { etiquetaGlobo } from '../puro/globo';
import { EN } from './en';
import { ES } from './es';
import { CLAVE_IDIOMA, I18nService } from './i18n.service';
import { T_ES, crearTraductor, localeDe } from './traducir';

const marcadores = (texto: string): string[] => [...texto.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

const T_EN = crearTraductor('en');

describe('diccionarios (AC-1)', () => {
  it('el inglés tiene exactamente las mismas claves que el español', () => {
    expect(Object.keys(EN).sort()).toEqual(Object.keys(ES).sort());
  });

  it('cada clave lleva los mismos marcadores {n} en los dos idiomas', () => {
    for (const clave of Object.keys(ES) as (keyof typeof ES)[]) {
      expect(marcadores(EN[clave]), clave).toEqual(marcadores(ES[clave]));
    }
  });

  it('ninguna traducción está vacía', () => {
    for (const [clave, texto] of Object.entries(ES)) expect(texto.trim(), `es:${clave}`).not.toBe('');
    for (const [clave, texto] of Object.entries(EN)) expect(texto.trim(), `en:${clave}`).not.toBe('');
  });

  it('el inglés no repite por descuido el texto español de las frases largas', () => {
    for (const clave of Object.keys(ES) as (keyof typeof ES)[]) {
      if (ES[clave].length > 40) expect(EN[clave], clave).not.toBe(ES[clave]);
    }
  });
});

describe('crearTraductor', () => {
  it('sustituye los marcadores y deja intacto el que no recibe valor', () => {
    expect(T_ES('tabla.pagina', { pagina: 2, paginas: 5 })).toBe('Página 2 de 5');
    expect(T_EN('tabla.pagina', { pagina: 2, paginas: 5 })).toBe('Page 2 of 5');
    expect(T_EN('tabla.pagina', { pagina: 2 })).toBe('Page 2 of {paginas}');
  });

  it('quita el punto final del motivo para no escribir «(…).).»', () => {
    expect(T_ES('tabla.error_actualizar', { motivo: 'La API no responde (red).' })).toBe(
      'No se pudo actualizar la tabla (La API no responde (red)).',
    );
  });

  it('cada traductor conoce su idioma y su configuración regional', () => {
    expect(T_ES.idioma).toBe('es');
    expect(T_EN.idioma).toBe('en');
    expect(localeDe('es')).toBe('es-ES');
    expect(localeDe('en')).toBe('en-GB');
  });
});

describe('números, fechas y textos en inglés (FR-004, FR-005)', () => {
  it('coma decimal en español y punto en inglés; ND pasa a N/A', () => {
    expect(formatearDecimal(4.5, 1)).toBe('4,5');
    expect(formatearDecimal(4.5, 1, T_EN)).toBe('4.5');
    expect(formatearMagnitud(2.1, T_EN)).toBe('2.1');
    expect(formatearProfundidad(10.5, T_EN)).toBe('10.5 km');
    expect(formatearMagnitud(null, T_ES)).toBe('ND');
    expect(formatearMagnitud(null, T_EN)).toBe('N/A');
  });

  it('los instantes siguen en UTC en los dos idiomas', () => {
    const iso = '2026-11-02T15:41:58.000Z';
    expect(formatearInstanteUtc(iso)).toBe('02/11/2026 15:41:58 UTC');
    expect(formatearInstanteUtc(iso, T_EN)).toBe('2 Nov 2026 15:41:58 UTC');
    expect(etiquetaVentanaUtc('2026-11-01T16:00:00Z', T_EN)).toBe('1 Nov 16:00 UTC');
  });

  it('los mensajes de validación, los errores y los avisos siguen el idioma', () => {
    const v = validarFiltros({ ...FILTROS_VACIOS, magnitudMin: 'x' }, T_EN);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.errores.magnitudMin).toBe('Enter a number between −10 and 10.');
    expect(clasificarError({ status: 0 }, T_EN).motivo).toContain('not responding');
    expect(clasificarError({ status: 418 }, T_EN).motivo).toContain('418');
    expect(textoAviso('base_fallida', T_EN)).toContain('database');
    expect(notaOrigenDatos({ modo: 'replay', sinteticos: false }, T_EN)).toContain('REPLAY');
  });

  const evento: PropiedadesEventoMapa = {
    event_id: 'us7000abcd',
    ocurrencia: '2026-11-02T10:15:30.000Z',
    updated: '2026-11-02T11:00:00.000Z',
    magnitud: 4.5,
    profundidad: 10,
    pais_nombre: 'México',
    sintetico: false,
    reproducido_en: null,
  };

  it('la ficha y el resumen del mapa salen en inglés; el país del catálogo no se traduce', () => {
    const ficha = crearFicha(evento, document, T_EN);
    const texto = ficha.textContent ?? '';
    expect(ficha.querySelector('.ficha__titulo')?.textContent).toBe('Magnitude 4.5');
    expect(texto).toContain('Occurrence');
    expect(texto).toContain('USGS identifier');
    expect(texto).toContain('2 Nov 2026 10:15:30 UTC');
    expect(texto).toContain('México');
    expect(ficha.getAttribute('aria-label')).toBe('Card of earthquake us7000abcd');
    expect(crearResumen(evento, document, T_EN).textContent).toBe('M 4.5, México');
  });

  it('«Sin país asignado» y «SINTÉTICO» se traducen en la interfaz', () => {
    const mar = { ...evento, pais_nombre: 'Sin país asignado', sintetico: true };
    expect(crearFicha(mar, document, T_EN).querySelector('.ficha__lugar')?.textContent).toBe(
      'No country assigned (at sea or outside borders)',
    );
    expect(crearFicha(mar, document, T_EN).querySelector('.ficha__marca')?.textContent).toBe('SYNTHETIC');
    expect(crearResumen(mar, document, T_EN).textContent).toBe('SYNTHETIC: M 4.5, no country assigned');
    expect(etiquetaGlobo(mar, T_EN)).toContain('SYNTHETIC');
    expect(etiquetaGlobo(mar, T_EN)).toContain('No country assigned');
  });
});

describe('I18nService (servicio de AC-2)', () => {
  afterEach(() => {
    localStorage.clear();
    document.documentElement.lang = 'es';
  });

  it('por defecto español, sin escribir nada en localStorage', () => {
    const i18n = TestBed.inject(I18nService);
    expect(i18n.idioma()).toBe('es');
    expect(document.documentElement.lang).toBe('es');
    expect(localStorage.getItem(CLAVE_IDIOMA)).toBeNull();
    expect(i18n.tr('cabecera.titulo')).toBe('Observatorio de actividad sísmica');
  });

  it('al cambiar a inglés cambian los textos, `lang` y el título, y se guarda la elección', () => {
    const i18n = TestBed.inject(I18nService);
    i18n.fijar('en');
    expect(i18n.tr('cabecera.titulo')).toBe('Seismic activity observatory');
    expect(i18n.entero(1234567)).toBe('1,234,567');
    expect(document.documentElement.lang).toBe('en');
    expect(document.title).toBe('Seismic activity observatory');
    expect(localStorage.getItem(CLAVE_IDIOMA)).toBe('en');
  });

  it('al recargar el servicio se recupera la elección', () => {
    TestBed.inject(I18nService).fijar('en');
    TestBed.resetTestingModule();
    const recargado = TestBed.inject(I18nService);
    expect(recargado.idioma()).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('un valor guardado que no es un idioma se ignora', () => {
    localStorage.setItem(CLAVE_IDIOMA, 'fr');
    expect(TestBed.inject(I18nService).idioma()).toBe('es');
  });

  it('el motivo de un error se rehace en inglés a partir de su tipo y en español usa el guardado', () => {
    const i18n = TestBed.inject(I18nService);
    const error = clasificarError({ status: 503 });
    expect(i18n.motivo(error)).toBe(error.motivo);
    i18n.fijar('en');
    expect(i18n.motivo(error)).toBe('Service unavailable: the database is not responding.');
  });
});
