import { T_ES, Traductor } from '../../i18n/traducir';
import { PropiedadesEventoMapa } from '../../modelos/api';
import { intervaloProfundidad } from '../../puro/escalas';
import { formatearInstanteUtc, formatearMagnitud, formatearProfundidad, textoNd } from '../../puro/formato';

const SIN_PAIS = 'Sin país asignado';

/** Lugar legible: el país (dato, no se traduce), o una explicación breve si el punto no cae en ningún polígono. */
function lugar(p: PropiedadesEventoMapa, t: Traductor): string {
  if (!p.pais_nombre || p.pais_nombre === SIN_PAIS) return t('dominio.sin_pais_mar');
  return p.pais_nombre;
}

/**
 * Ficha del terremoto para el popup de Leaflet. Se construye con nodos DOM y `textContent`
 * (nunca `innerHTML`): ningún texto de la API se interpreta como HTML.
 */
export function crearFicha(
  p: PropiedadesEventoMapa,
  doc: Document = document,
  t: Traductor = T_ES,
): HTMLElement {
  const raiz = doc.createElement('div');
  raiz.className = 'ficha';
  raiz.setAttribute('role', 'group');
  raiz.setAttribute(
    'aria-label',
    t(p.sintetico ? 'ficha.aria_sintetico' : 'ficha.aria_real', { id: p.event_id }),
  );

  const titulo = doc.createElement('h3');
  titulo.className = 'ficha__titulo';
  titulo.textContent = t('ficha.titulo', { magnitud: formatearMagnitud(p.magnitud, t) });
  if (p.magnitud === null) titulo.classList.add('nd');
  if (p.sintetico) {
    // Marca de texto (no solo color): un caso de prueba nunca debe pasar por un terremoto real.
    const marca = doc.createElement('span');
    marca.className = 'ficha__marca';
    marca.textContent = t('dominio.sintetico');
    titulo.append(' ', marca);
  }
  raiz.append(titulo);

  const sitio = doc.createElement('p');
  sitio.className = 'ficha__lugar';
  sitio.textContent = lugar(p, t);
  raiz.append(sitio);

  const lista = doc.createElement('dl');
  lista.className = 'ficha__datos';
  const filas: { rotulo: string; valor: string; color?: string; esId?: boolean }[] = [
    { rotulo: t('ficha.ocurrencia'), valor: formatearInstanteUtc(p.ocurrencia, t) },
    {
      rotulo: t('ficha.profundidad'),
      valor: formatearProfundidad(p.profundidad, t),
      color: intervaloProfundidad(p.profundidad)?.color,
    },
    { rotulo: t('ficha.actualizado'), valor: formatearInstanteUtc(p.updated, t) },
  ];
  // Solo en REPRODUCCIÓN (en directo es `null`): «Ocurrencia» sigue siendo el tiempo original.
  if (p.reproducido_en != null) {
    filas.splice(1, 0, { rotulo: t('ficha.reproducido'), valor: formatearInstanteUtc(p.reproducido_en, t) });
  }
  filas.push({ rotulo: t('ficha.id'), valor: p.event_id, esId: true });
  const nd = textoNd(t);
  for (const { rotulo, valor, color, esId } of filas) {
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
    if (valor === nd) dd.classList.add('nd');
    if (esId) dd.classList.add('ficha__id');
    lista.append(dt, dd);
  }
  raiz.append(lista);
  return raiz;
}

/** Resumen de una línea al pasar el ratón: magnitud y lugar. Mismo cuidado que la ficha: solo texto. */
export function crearResumen(
  p: PropiedadesEventoMapa,
  doc: Document = document,
  t: Traductor = T_ES,
): HTMLElement {
  const el = doc.createElement('span');
  const prefijo = p.sintetico ? `${t('dominio.sintetico')}: ` : '';
  const sitio = !p.pais_nombre || p.pais_nombre === SIN_PAIS ? t('ficha.resumen_sin_pais') : p.pais_nombre;
  el.textContent = `${prefijo}M ${formatearMagnitud(p.magnitud, t)}, ${sitio}`;
  return el;
}
