import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'start' },
  {
    path: 'start',
    loadComponent: () =>
      import('./features/start/components/start/start.component').then((m) => m.StartComponent),
  },
  {
    path: 'game/new',
    loadComponent: () =>
      import('./features/game/components/game-setup/game-setup.component').then(
        (m) => m.GameSetupComponent,
      ),
  },
  {
    path: 'game',
    loadComponent: () =>
      import('./features/game/components/game/game.component').then((m) => m.GameComponent),
  },
  {
    path: 'capture',
    loadComponent: () =>
      import('./features/capture/components/capture/capture.component').then((m) => m.CaptureComponent),
  },
  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/components/settings/settings.component').then((m) => m.SettingsComponent),
  },
  { path: '**', redirectTo: 'start' },
];
