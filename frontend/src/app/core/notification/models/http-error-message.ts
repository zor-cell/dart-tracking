import { HttpErrorResponse } from '@angular/common/http';
import { tooManyRequestsMessage } from './too-many-requests';

/** A message for a status, or one picked from the response (its `detail`, say). */
export type StatusMessage = string | ((error: HttpErrorResponse) => string);

/** German text for a failed request: the status's own message, a 429's wait, or `fallback`. */
export function httpErrorMessage(
  failure: unknown,
  messages: Readonly<Partial<Record<number, StatusMessage>>>,
  fallback: string,
): string {
  if (!(failure instanceof HttpErrorResponse)) {
    return fallback;
  }
  const message = messages[failure.status];
  if (message !== undefined) {
    return typeof message === 'function' ? message(failure) : message;
  }
  return failure.status === 429 ? tooManyRequestsMessage(failure) : fallback;
}
