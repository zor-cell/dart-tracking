import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Waits for the session restore before deciding, so a reload on a guarded
 * route does not bounce to the login screen while the cookie is still in
 * flight. Sends the attempted url along, to return to it after signing in. */
export const authGuard: CanActivateFn = async (_route, state) => {
  // Both injections happen before the await: an injection context does not
  // survive one.
  const auth = inject(AuthService);
  const router = inject(Router);

  await auth.ready;

  return (
    auth.isAuthenticated() ||
    router.createUrlTree(['/login'], { queryParams: { redirect: state.url } })
  );
};
