import {
  HttpContext,
  HttpContextToken,
  HttpErrorResponse,
  HttpInterceptorFn,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from '../features/auth/services/auth.service';
import { NotificationService } from './notification/services/notification.service';

/**
 * A context token for silent error handling
 */
export const SILENT_ERROR_HANDLER = new HttpContextToken<boolean>(() => false);

/**
 * A context variable that can be appended as a request context to not show the error banner on error
 */
export const SILENT_ERROR_CONTEXT = new HttpContext().set(SILENT_ERROR_HANDLER, true);

/** Marks the auth calls themselves, which are neither gated nor retried. */
export const SKIP_AUTH_RETRY = new HttpContextToken<boolean>(() => false);

/**
 * Intercepts all HTTP responses and shows an error banner if the response was an error
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const notification = inject(NotificationService);

  const silentErrorHandling = req.context.get(SILENT_ERROR_HANDLER);
  return next(req).pipe(
    catchError((err) => {
      if (!silentErrorHandling) {
        notification.showError(err);
      }

      return throwError(() => err);
    }),
  );
};

/**
 * Signs each request with the access token and, on a 401, trades the refresh
 * cookie for a new one and repeats the request once. Runs inside
 * `errorInterceptor` and waits for the restore.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  const sign = () => {
    const token = auth.accessToken();
    return token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
  };

  // The auth calls themselves: the restore is one of them, so waiting on it
  // here would deadlock, and their 401 is an answer rather than an expiry.
  if (req.context.get(SKIP_AUTH_RETRY)) {
    return next(sign());
  }

  return from(auth.ready).pipe(
    switchMap(() => next(sign())),
    catchError((err) => {
      if (!(err instanceof HttpErrorResponse) || err.status !== 401) {
        return throwError(() => err);
      }

      return from(auth.refresh()).pipe(
        switchMap((token) => (token ? next(sign()) : throwError(() => err))),
      );
    }),
  );
};
