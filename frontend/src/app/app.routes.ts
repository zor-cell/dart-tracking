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
      import('./features/game/components/game-new/game-new.component').then(
        (m) => m.GameNewComponent,
      ),
  },
  {
    path: 'game/join/:gameId',
    loadComponent: () =>
      import('./features/game/components/game-join/game-join.component').then(
        (m) => m.GameJoinComponent,
      ),
  },
  {
    path: 'game',
    loadComponent: () =>
      import('./features/game/components/game/game.component').then((m) => m.GameComponent),
  },
  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/components/settings/settings.component').then((m) => m.SettingsComponent),
  },
  { path: '**', redirectTo: 'start' },
];
