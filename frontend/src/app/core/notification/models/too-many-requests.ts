import { HttpErrorResponse } from '@angular/common/http';

/** German text for a 429, naming the wait when the server sent `Retry-After` (seconds). */
export function tooManyRequestsMessage(error: HttpErrorResponse): string {
  const seconds = Number(error.headers.get('Retry-After'));
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return 'Zu viele Anfragen. Bitte kurz warten und erneut versuchen.';
  }
  if (seconds <= 90) {
    return `Zu viele Versuche. Bitte in ${Math.ceil(seconds)} Sekunden erneut versuchen.`;
  }
  return `Zu viele Versuche. Bitte in ${Math.ceil(seconds / 60)} Minuten erneut versuchen.`;
}
