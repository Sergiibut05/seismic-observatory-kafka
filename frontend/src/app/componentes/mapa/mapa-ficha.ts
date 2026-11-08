import { PropiedadesEventoMapa } from '../../modelos/api';
import { formatearInstanteUtc, formatearMagnitud, formatearProfundidad, ND } from '../../puro/formato';

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

  const lista = doc.createElement('dl');
  lista.className = 'ficha__datos';
  const filas: [string, string][] = [
    ['Identificador', p.event_id],
    ['Ocurrencia', formatearInstanteUtc(p.ocurrencia)],
    ['Actualizado', formatearInstanteUtc(p.updated)],
    ['Magnitud', formatearMagnitud(p.magnitud)],
    ['Profundidad', formatearProfundidad(p.profundidad)],
    ['País', p.pais_nombre || ND],
  ];
  // Solo en REPRODUCCIÓN (en directo es `null`): «Ocurrencia» sigue siendo el tiempo original.
  if (p.reproducido_en != null) {
    filas.splice(2, 0, ['Reproducido', formatearInstanteUtc(p.reproducido_en)]);
  }
  for (const [rotulo, valor] of filas) {
    const dt = doc.createElement('dt');
    dt.textContent = rotulo;
    const dd = doc.createElement('dd');
    dd.textContent = valor;
    if (valor === ND) dd.classList.add('nd');
    lista.append(dt, dd);
  }
  raiz.append(lista);
  return raiz;
}
