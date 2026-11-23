import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { MessageService } from 'primeng/api';
import { tooManyRequestsMessage } from '../models/too-many-requests';

/** PrimeNG's own default, restated so callers can raise it per message. */
const DEFAULT_TOAST_LIFE = 3000;

/**
 * User-facing feedback as toasts, always with localized texts; backend `detail`
 * payloads are never shown.
 */
@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private messageService = inject(MessageService);

  showSuccess(message: string, title = $localize`:@@common.success:Erfolg`) {
    this.messageService.add({ severity: 'success', summary: title, detail: message });
  }

  showError(error: unknown, title = $localize`:@@common.error:Fehler`) {
    this.messageService.add({
      severity: 'error',
      summary: title,
      detail: this.describe(error),
    });
  }

  /** Show an error whose text is already user-facing, for `life` milliseconds. */
  showErrorMessage(
    message: string,
    title = $localize`:@@common.error:Fehler`,
    life = DEFAULT_TOAST_LIFE,
  ) {
    this.messageService.add({ severity: 'error', summary: title, detail: message, life });
  }

  showInfo(message: string, title = $localize`:@@common.info:Hinweis`, life = DEFAULT_TOAST_LIFE) {
    this.messageService.add({ severity: 'info', summary: title, detail: message, life });
  }

  showWarning(message: string, title = $localize`:@@common.warning:Warnung`) {
    this.messageService.add({ severity: 'warn', summary: title, detail: message });
  }

  private describe(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) {
      return $localize`:@@common.unknownError:Unbekannter Fehler.`;
    }
    if (error.status === 0) {
      return $localize`:@@common.offline:Keine Verbindung zum Server. Bitte Netzwerk prüfen und erneut versuchen.`;
    }
    if (error.status === 404) {
      return $localize`:@@common.notFound:Der angeforderte Eintrag wurde nicht gefunden.`;
    }
    if (error.status === 429) {
      return tooManyRequestsMessage(error);
    }
    if (error.status === 422 || error.status === 400) {
      return $localize`:@@common.invalidInput:Die Eingabe ist ungültig.`;
    }
    if (error.status >= 500) {
      return $localize`:@@common.serverError:Serverfehler. Bitte später erneut versuchen.`;
    }
    return $localize`:@@common.requestFailed:Die Anfrage konnte nicht verarbeitet werden.`;
  }
}
