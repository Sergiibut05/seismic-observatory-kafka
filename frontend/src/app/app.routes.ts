import { Routes } from '@angular/router';

// El panel es una sola pantalla: la ruta vacía no carga ningún componente (la app los coloca)
// y cualquier otra URL vuelve a ella.
export const routes: Routes = [
  { path: '', pathMatch: 'full', children: [] },
  { path: '**', redirectTo: '' },
];
