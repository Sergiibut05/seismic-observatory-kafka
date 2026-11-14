// Fuentes de un evento (013): «EMSC + USGS». Los nombres de las fuentes son siglas y no se traducen.

/** Siglas en mayúsculas, en orden alfabético y unidas con « + »; cadena vacía si no hay fuentes. */
export function textoFuentes(fuentes: readonly string[] | null | undefined): string {
  if (!fuentes?.length) return '';
  return [...new Set(fuentes)]
    .sort()
    .map((f) => f.toUpperCase())
    .join(' + ');
}
