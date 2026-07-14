import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'capture',
    loadComponent: () =>
      import('./features/capture/components/capture/capture.component').then((m) => m.CaptureComponent),
  },
];
