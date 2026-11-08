import { PropiedadesEventoMapa } from '../../modelos/api';
import { intervaloProfundidad } from '../../puro/escalas';
import { formatearInstanteUtc, formatearMagnitud, formatearProfundidad, ND } from '../../puro/formato';

const SIN_PAIS = 'Sin país asignado';

/** Lugar legible: el país, o una explicación breve si el punto no cae en ningún polígono. */
function lugar(p: PropiedadesEventoMapa): string {
  if (!p.pais_nombre || p.pais_nombre === SIN_PAIS) return `${SIN_PAIS} (mar o fuera de fronteras)`;
  return p.pais_nombre;
}

/**
 * Ficha del terremoto para el popup de Leaflet. Se construye con nodos DOM y `textContent`
 * (nunca `innerHTML`): ningún texto de la API se interpreta como HTML.
 */
export function crearFicha(p: PropiedadesEventoMapa, doc: Document = document): HTMLElement {
  const raiz = doc.createElement('div');
  raiz.className = 'ficha';
  raiz.setAttribute('role', 'group');
  raiz.setAttribute(
    'aria-label',
    p.sintetico ? `Ficha del caso de prueba sintético ${p.event_id}` : `Ficha del terremoto ${p.event_id}`,
  );

  const titulo = doc.createElement('h3');
  titulo.className = 'ficha__titulo';
  titulo.textContent = `Magnitud ${formatearMagnitud(p.magnitud)}`;
  if (p.magnitud === null) titulo.classList.add('nd');
  if (p.sintetico) {
    // Marca de texto (no solo color): un caso de prueba nunca debe pasar por un terremoto real.
    const marca = doc.createElement('span');
    marca.className = 'ficha__marca';
    marca.textContent = 'SINTÉTICO';
    titulo.append(' ', marca);
  }
  raiz.append(titulo);

  const sitio = doc.createElement('p');
  sitio.className = 'ficha__lugar';
  sitio.textContent = lugar(p);
  raiz.append(sitio);

  const lista = doc.createElement('dl');
  lista.className = 'ficha__datos';
  const filas: [string, string, string?][] = [
    ['Ocurrencia', formatearInstanteUtc(p.ocurrencia)],
    ['Profundidad', formatearProfundidad(p.profundidad), intervaloProfundidad(p.profundidad)?.color],
    ['Actualizado', formatearInstanteUtc(p.updated)],
  ];
  // Solo en REPRODUCCIÓN (en directo es `null`): «Ocurrencia» sigue siendo el tiempo original.
  if (p.reproducido_en != null) {
    filas.splice(1, 0, ['Reproducido', formatearInstanteUtc(p.reproducido_en)]);
  }
  filas.push(['Identificador USGS', p.event_id]);
  for (const [rotulo, valor, color] of filas) {
    const dt = doc.createElement('dt');
    dt.textContent = rotulo;
    const dd = doc.createElement('dd');
    if (color) {
      const muestra = doc.createElement('span');
      muestra.className = 'ficha__muestra';
      muestra.style.background = color;
      muestra.setAttribute('aria-hidden', 'true');
      dd.append(muestra);
    }
    dd.append(valor);
    if (valor === ND) dd.classList.add('nd');
    if (rotulo === 'Identificador USGS') dd.classList.add('ficha__id');
    lista.append(dt, dd);
  }
  raiz.append(lista);
  return raiz;
}

/** Resumen de una línea al pasar el ratón: magnitud y lugar. Mismo cuidado que la ficha: solo texto. */
export function crearResumen(p: PropiedadesEventoMapa, doc: Document = document): HTMLElement {
  const el = doc.createElement('span');
  const prefijo = p.sintetico ? 'SINTÉTICO: ' : '';
  const sitio = !p.pais_nombre || p.pais_nombre === SIN_PAIS ? 'sin país asignado' : p.pais_nombre;
  el.textContent = `${prefijo}M ${formatearMagnitud(p.magnitud)}, ${sitio}`;
  return el;
}
