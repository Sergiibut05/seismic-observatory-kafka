// Traducción pura (sin Angular): los diccionarios y la sustitución de marcadores `{nombre}`.
import { EN } from './en';
import { Clave, ES } from './es';

export type Idioma = 'es' | 'en';
export const IDIOMAS: readonly Idioma[] = ['es', 'en'];
export const IDIOMA_POR_DEFECTO: Idioma = 'es';

export type ParametrosTraduccion = Record<string, string | number>;

/** `idioma` va en el propio traductor para que los números y las fechas sigan al texto sin otro parámetro. */
export interface Traductor {
  (clave: Clave, parametros?: ParametrosTraduccion): string;
  readonly idioma: Idioma;
}

const DICCIONARIOS: Record<Idioma, Record<Clave, string>> = { es: ES, en: EN };

export function esIdioma(valor: unknown): valor is Idioma {
  return valor === 'es' || valor === 'en';
}

/** Configuración regional de `Intl`: coma decimal en español, punto en inglés. */
export function localeDe(idioma: Idioma): string {
  return idioma === 'en' ? 'en-GB' : 'es-ES';
}

export function crearTraductor(idioma: Idioma): Traductor {
  const diccionario = DICCIONARIOS[idioma];
  const traducir = (clave: Clave, parametros?: ParametrosTraduccion): string => {
    const texto = diccionario[clave];
    if (!parametros) return texto;
    return texto.replace(/\{(\w+)\}/g, (marcador, nombre: string) => {
      if (!(nombre in parametros)) return marcador;
      const valor = String(parametros[nombre]);
      // Un motivo es una frase completa con su punto; dentro de «(…).» el punto sobra.
      return nombre === 'motivo' ? valor.replace(/\.$/, '') : valor;
    });
  };
  return Object.assign(traducir, { idioma });
}

/** Traductor por defecto de las funciones puras: los tests existentes siguen en español. */
export const T_ES: Traductor = crearTraductor('es');
