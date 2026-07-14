import {HttpContext, HttpContextToken, HttpInterceptorFn} from "@angular/common/http";
import {inject} from "@angular/core";
import {catchError, throwError} from "rxjs";
import {NotificationService} from "./services/notification.service";

/**
 * A context token for silent error handling
 */
const SILENT_ERROR_HANDLER = new HttpContextToken<boolean>(() => false);

/**
 * A context variable that can be appended as a request context to not show the error banner on error
 */
export const SILENT_ERROR_CONTEXT = new HttpContext().set(SILENT_ERROR_HANDLER, true);

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