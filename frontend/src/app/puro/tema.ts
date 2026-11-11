// Temas de la identidad 011: papel (por defecto) y noche.
export type Tema = 'papel' | 'noche';

export const TEMA_POR_DEFECTO: Tema = 'papel';

export function esTema(valor: unknown): valor is Tema {
  return valor === 'papel' || valor === 'noche';
}
