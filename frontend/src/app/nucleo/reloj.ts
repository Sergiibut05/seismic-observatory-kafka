import { InjectionToken } from '@angular/core';

/** Reloj en ms epoch; se sustituye en los tests. */
export const RELOJ = new InjectionToken<() => number>('RELOJ', {
  providedIn: 'root',
  factory: () => () => Date.now(),
});
