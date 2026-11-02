// Tipos de la API 0.2.0 (docs/CONTRATO-API.md). Solo campos documentados.
// Un dato desconocido es `null`, nunca 0: los componentes deben pintarlo «ND».

/** Instante UTC ISO 8601 con `Z` y milisegundos. */
export type InstanteUtc = string;

export interface EstadoApi {
  base_de_datos: 'conectada' | 'fallida';
  eventos_reales: number | null;
  eventos_sinteticos: number | null;
  ultimo_evento: {
    event_id: string;
    updated: InstanteUtc;
    source: string;
    sintetico: boolean;
    processed_at: InstanteUtc;
  } | null;
  ultima_ingesta_correcta: InstanteUtc | null;
  periodo_consultado: { desde: InstanteUtc; hasta: InstanteUtc } | null;
  datos_desactualizados: boolean | null;
  umbral_datos_desactualizados_segundos: number;
  generated_at: InstanteUtc;
}

export interface EventoTabla {
  event_id: string;
  ocurrencia: InstanteUtc;
  updated: InstanteUtc;
  magnitud: number | null;
  profundidad: number | null;
  longitud: number;
  latitud: number;
  pais_codigo: string | null;
  pais_nombre: string;
  subregion: string | null;
  sintetico: boolean;
}

export interface RespuestaEventos {
  eventos: EventoTabla[];
  total: number;
  limite: number;
  desplazamiento: number;
}

export interface PropiedadesEventoMapa {
  event_id: string;
  ocurrencia: InstanteUtc;
  updated: InstanteUtc;
  magnitud: number | null;
  profundidad: number | null;
  pais_nombre: string;
  sintetico: boolean;
}

export interface EventoMapa {
  type: 'Feature';
  /** Coordenadas `[longitud, latitud]`. */
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: PropiedadesEventoMapa;
}

export interface RespuestaMapa {
  type: 'FeatureCollection';
  features: EventoMapa[];
  total: number;
  devueltos: number;
  limite: number;
  truncado: boolean;
  generated_at: InstanteUtc;
}

export interface CategoriaPais {
  codigo: string | null;
  nombre: string;
  recuento: number;
}

export interface CategoriaSubregion {
  nombre: string;
  recuento: number;
}

export interface RecuentosPais {
  total: number;
  categorias: CategoriaPais[];
}

export interface RecuentosSubregion {
  total: number;
  categorias: CategoriaSubregion[];
}

export interface VentanaHora {
  inicio: InstanteUtc;
  recuento: number;
}

export interface RecuentosHora {
  desde: InstanteUtc;
  hasta: InstanteUtc;
  total: number;
  ventanas: VentanaHora[];
}

export interface IntervaloDistribucion {
  desde: number | null;
  hasta: number | null;
  etiqueta: string;
  recuento: number;
}

export interface Distribucion {
  unidad: 'magnitud' | 'km';
  total: number;
  sin_valor: number;
  intervalos: IntervaloDistribucion[];
}

export interface FiltrosEfectivos {
  magnitud_min: number | null;
  magnitud_max: number | null;
  pais: string | null;
  subregion: string | null;
}

export interface ComparacionHistorica {
  ventana_actual: { desde: InstanteUtc; hasta: InstanteUtc; eventos: number };
  historico_2025: {
    estado: 'cargado' | 'no_cargado';
    eventos: number | null;
    dias: number;
    media_diaria: number | null;
  };
  cociente: number | null;
  filtros_efectivos: FiltrosEfectivos;
  aviso: string;
  generated_at: InstanteUtc;
}
