import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Admin-only routes. A signed-in non-admin goes to the account page rather
 * than the login screen: signing in again would not help them. */
export const adminGuard: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  await auth.ready;

  if (auth.isAdmin()) {
    return true;
  }
  return auth.isAuthenticated()
    ? router.createUrlTree(['/account'])
    : router.createUrlTree(['/login'], { queryParams: { redirect: state.url } });
};
