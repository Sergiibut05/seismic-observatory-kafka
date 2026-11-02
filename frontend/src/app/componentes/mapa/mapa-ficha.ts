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
  raiz.setAttribute('aria-label', `Ficha del terremoto ${p.event_id}`);

  const titulo = doc.createElement('h3');
  titulo.className = 'ficha__titulo';
  titulo.textContent = `Magnitud ${formatearMagnitud(p.magnitud)}`;
  if (p.magnitud === null) titulo.classList.add('nd');
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
