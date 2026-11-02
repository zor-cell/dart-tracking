import { Injectable, inject } from '@angular/core';
import { ConfirmationService } from 'primeng/api';

/** Asks before an action, in the one confirm dialog the app shell renders. */
@Injectable({ providedIn: 'root' })
export class ConfirmService {
  private readonly confirmation = inject(ConfirmationService);

  /** `action` labels the button, red unless the action is `safe`; `accept` runs once it is
   * pressed. */
  ask(header: string, message: string, action: string, accept: () => void, safe = false): void {
    this.confirmation.confirm({
      header,
      message,
      icon: safe ? 'pi pi-question-circle' : 'pi pi-exclamation-triangle',
      rejectButtonProps: {
        label: $localize`:@@common.cancel:Abbrechen`,
        severity: 'secondary',
        text: true,
      },
      acceptButtonProps: { label: action, severity: safe ? 'primary' : 'danger' },
      accept,
    });
  }
}
