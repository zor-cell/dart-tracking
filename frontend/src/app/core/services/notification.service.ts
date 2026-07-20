import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { MessageService } from 'primeng/api';

/**
 * User-facing feedback. All texts are German: the HTTP status is the protocol,
 * the message is presentation. Backend `detail` payloads are deliberately not
 * shown — they are English developer diagnostics (pydantic and Starlette emit
 * them too, and those cannot be translated), and they leak internals.
 */
@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private messageService = inject(MessageService);

  showSuccess(message: string, title = 'Erfolg') {
    this.messageService.add({ severity: 'success', summary: title, detail: message });
  }

  showError(error: unknown, title = 'Fehler') {
    this.messageService.add({
      severity: 'error',
      summary: title,
      detail: this.describe(error),
    });
  }

  showInfo(message: string, title = 'Hinweis') {
    this.messageService.add({ severity: 'info', summary: title, detail: message });
  }

  showWarning(message: string, title = 'Warnung') {
    this.messageService.add({ severity: 'warn', summary: title, detail: message });
  }

  private describe(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) {
      return 'Unbekannter Fehler.';
    }
    if (error.status === 0) {
      return 'Keine Verbindung zum Server. Bitte Netzwerk prüfen und erneut versuchen.';
    }
    if (error.status === 404) {
      return 'Der angeforderte Eintrag wurde nicht gefunden.';
    }
    if (error.status === 422 || error.status === 400) {
      return 'Die Eingabe ist ungültig.';
    }
    if (error.status >= 500) {
      return 'Serverfehler. Bitte später erneut versuchen.';
    }
    return 'Die Anfrage konnte nicht verarbeitet werden.';
  }
}
