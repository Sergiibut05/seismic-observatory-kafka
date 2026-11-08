import { Injectable, computed, signal } from '@angular/core';
import { Clave } from '../i18n/es';

/** `motivo` es la frase en español (logs y tests); `clave` permite mostrarla en el idioma vigente. */
export type ResultadoUrlBase = { ok: true; url: string } | { ok: false; motivo: string; clave: Clave };

const HOSTS_LOCALES = new Set(['localhost', '127.0.0.1']);

/** HTTPS siempre; `http` solo en localhost/127.0.0.1. Sin ruta, consulta ni credenciales. */
export function validarUrlBase(valor: unknown): ResultadoUrlBase {
  if (typeof valor !== 'string' || !valor.trim()) {
    return { ok: false, motivo: 'Falta «apiBaseUrl» en config.json.', clave: 'config.falta_url' };
  }
  const sinBarra = valor.trim().replace(/\/+$/, '');
  let url: URL;
  try {
    url = new URL(sinBarra);
  } catch {
    return { ok: false, motivo: '«apiBaseUrl» no es una URL válida.', clave: 'config.url_invalida' };
  }
  const local = HOSTS_LOCALES.has(url.hostname);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) {
    return {
      ok: false,
      motivo: '«apiBaseUrl» debe usar HTTPS (http solo en localhost o 127.0.0.1).',
      clave: 'config.url_https',
    };
  }
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    return {
      ok: false,
      motivo: '«apiBaseUrl» debe ser solo el origen de la API, sin ruta ni credenciales.',
      clave: 'config.url_origen',
    };
  }
  // El marcador de config.ejemplo.json no es un destino real.
  if (url.hostname.toLowerCase().startsWith('subdominio.')) {
    return {
      ok: false,
      motivo: '«apiBaseUrl» aún tiene el marcador SUBDOMINIO: pega la URL de ngrok.',
      clave: 'config.url_marcador',
    };
  }
  return { ok: true, url: sinBarra };
}

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly _apiBaseUrl = signal<string | null>(null);
  private readonly _error = signal<string | null>(null);
  private readonly _errorClave = signal<Clave | null>(null);

  /** URL base validada, o `null` si la configuración no es válida. */
  readonly apiBaseUrl = this._apiBaseUrl.asReadonly();
  /** Motivo del fallo de configuración (en español), o `null`. */
  readonly error = this._error.asReadonly();
  /** Clave del diccionario del mismo motivo, para mostrarlo en el idioma vigente. */
  readonly errorClave = this._errorClave.asReadonly();
  readonly valida = computed(() => this._apiBaseUrl() !== null);

  /** Lee `config.json` (sin caché). Nunca lanza: deja el motivo en `error`. */
  async cargar(): Promise<void> {
    try {
      const respuesta = await fetch('config.json', { cache: 'no-store' });
      if (!respuesta.ok) {
        this.fallar('No se pudo leer config.json.', 'config.no_se_pudo_leer');
        return;
      }
      const cuerpo: unknown = await respuesta.json();
      const crudo =
        typeof cuerpo === 'object' && cuerpo !== null
          ? (cuerpo as Record<string, unknown>)['apiBaseUrl']
          : undefined;
      const r = validarUrlBase(crudo);
      if (r.ok) {
        this._apiBaseUrl.set(r.url);
        this._error.set(null);
        this._errorClave.set(null);
      } else {
        this.fallar(r.motivo, r.clave);
      }
    } catch {
      this.fallar('config.json no se pudo leer o no es un JSON válido.', 'config.json_invalido');
    }
  }

  private fallar(motivo: string, clave: Clave): void {
    this._apiBaseUrl.set(null);
    this._error.set(motivo);
    this._errorClave.set(clave);
    console.error(`service=panel result=error componente=config motivo="${motivo}"`);
  }
}
