import { Injectable, inject } from '@angular/core';
import { ConfirmationService } from 'primeng/api';

/** Asks before a destructive action, in the one confirm dialog the app shell renders. */
@Injectable({ providedIn: 'root' })
export class ConfirmService {
  private readonly confirmation = inject(ConfirmationService);

  /** `action` labels the red button; `accept` runs once it is pressed. */
  ask(header: string, message: string, action: string, accept: () => void): void {
    this.confirmation.confirm({
      header,
      message,
      icon: 'pi pi-exclamation-triangle',
      rejectButtonProps: { label: 'Abbrechen', severity: 'secondary', text: true },
      acceptButtonProps: { label: action, severity: 'danger' },
      accept,
    });
  }
}
