import { httpErrorMessage } from '../../../core/notification/models/http-error-message';

/** The message for a failed create or rename of an address-book entry. */
export function playerNameError(failure: unknown): string {
  return httpErrorMessage(
    failure,
    { 409: 'Diesen Namen gibt es schon in deiner Spielerliste.' },
    'Speichern fehlgeschlagen. Bitte später erneut versuchen.',
  );
}
