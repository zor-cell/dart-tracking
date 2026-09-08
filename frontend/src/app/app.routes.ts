import { Routes } from '@angular/router';
import { adminGuard } from './features/auth/guards/admin.guard';
import { authGuard } from './features/auth/guards/auth.guard';

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
    path: 'login',
    loadComponent: () =>
      import('./features/auth/components/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'register',
    loadComponent: () =>
      import('./features/auth/components/register/register.component').then(
        (m) => m.RegisterComponent,
      ),
  },
  {
    path: 'account',
    loadComponent: () =>
      import('./features/auth/components/account/account.component').then(
        (m) => m.AccountComponent,
      ),
  },
  {
    path: 'account/stats',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/statistics/components/statistics/statistics.component').then(
        (m) => m.StatisticsComponent,
      ),
  },
  {
    path: 'account/settings',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/settings/components/settings/settings.component').then(
        (m) => m.SettingsComponent,
      ),
  },
  {
    path: 'account/evaluation',
    canActivate: [adminGuard],
    loadComponent: () =>
      import('./features/evaluation/components/evaluation/evaluation.component').then(
        (m) => m.EvaluationComponent,
      ),
  },
  { path: '**', redirectTo: 'start' },
];
