import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, model, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { tooManyRequestsMessage } from '../../../../core/notification/models/too-many-requests';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-change-password-dialog',
  imports: [ReactiveFormsModule, Button, Dialog, InputText, Message],
  templateUrl: './change-password-dialog.component.html',
  styleUrl: './change-password-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChangePasswordDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly notification = inject(NotificationService);

  readonly visible = model(false);

  protected readonly form = this.fb.nonNullable.group({
    currentPassword: ['', [Validators.required, Validators.maxLength(128)]],
    newPassword: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
  });

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async submit(): Promise<void> {
    if (this.form.invalid || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.auth.changePassword(this.form.getRawValue());
      this.notification.showSuccess('Passwort geändert. Andere Geräte wurden abgemeldet.');
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
    if (failure instanceof HttpErrorResponse) {
      if (failure.status === 403) {
        return 'Das aktuelle Passwort stimmt nicht.';
      }
      if (failure.status === 429) {
        return tooManyRequestsMessage(failure);
      }
    }
    return 'Speichern fehlgeschlagen. Bitte erneut versuchen.';
  }
}
