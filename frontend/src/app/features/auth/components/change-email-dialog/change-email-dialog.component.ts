import { ChangeDetectionStrategy, Component, inject, model, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { AuthService } from '../../services/auth.service';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';

@Component({
  selector: 'app-change-email-dialog',
  imports: [ReactiveFormsModule, Button, Dialog, InputText, Message, FieldErrorComponent],
  templateUrl: './change-email-dialog.component.html',
  styleUrl: './change-email-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChangeEmailDialogComponent {
  protected readonly dialogStyle = DIALOG_STYLE;
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly notification = inject(NotificationService);

  readonly visible = model(false);

  protected readonly form = this.fb.nonNullable.group({
    newEmail: ['', [Validators.required, Validators.email]],
    currentPassword: ['', [Validators.required, Validators.maxLength(128)]],
  });

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async submit(): Promise<void> {
    if (this.form.invalid || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    const change = this.form.getRawValue();
    try {
      await this.auth.requestEmailChange(change);
      this.notification.showInfo(
        `Bestätigungslink an ${change.newEmail} gesendet. Bis du ihn öffnest, bleibt deine bisherige Adresse aktiv.`,
      );
      this.visible.set(false);
    } catch (failure) {
      this.error.set(this.describe(failure));
    } finally {
      this.busy.set(false);
    }
  }

  protected reset(): void {
    this.form.reset();
    this.error.set(null);
  }

  private describe(failure: unknown): string {
    return httpErrorMessage(
      failure,
      {
        403: 'Das aktuelle Passwort stimmt nicht.',
        409: (error) =>
          error.error?.detail === 'email unchanged'
            ? 'Das ist bereits deine aktuelle Adresse.'
            : 'Diese Adresse wird bereits von einem anderen Konto verwendet.',
      },
      'Anfrage fehlgeschlagen. Bitte erneut versuchen.',
    );
  }
}
