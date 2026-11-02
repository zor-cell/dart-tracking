import { HttpErrorResponse } from '@angular/common/http';

/** Text for a 429, naming the wait when the server sent `Retry-After` (seconds). */
export function tooManyRequestsMessage(error: HttpErrorResponse): string {
  const seconds = Number(error.headers.get('Retry-After'));
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return $localize`:@@common.tooManyRequests:Zu viele Anfragen. Bitte kurz warten und erneut versuchen.`;
  }
  if (seconds <= 90) {
    return $localize`:@@common.retryInSeconds:Zu viele Versuche. Bitte in ${Math.ceil(seconds)}:seconds: Sekunden erneut versuchen.`;
  }
  return $localize`:@@common.retryInMinutes:Zu viele Versuche. Bitte in ${Math.ceil(seconds / 60)}:minutes: Minuten erneut versuchen.`;
}
