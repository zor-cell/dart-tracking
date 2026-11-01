import { ChangeDetectionStrategy, Component, inject, model, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { AuthService } from '../../services/auth.service';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';

/** Deletes the signed-in account once its password is entered again. */
@Component({
  selector: 'app-delete-account-dialog',
  imports: [ReactiveFormsModule, Button, Dialog, InputText, Message, FieldErrorComponent],
  templateUrl: './delete-account-dialog.component.html',
  styleUrl: './delete-account-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DeleteAccountDialogComponent {
  protected readonly dialogStyle = DIALOG_STYLE;
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly notification = inject(NotificationService);
  private readonly router = inject(Router);

  readonly visible = model(false);

  protected readonly form = this.fb.nonNullable.group({
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
    try {
      await this.auth.deleteAccount(this.form.getRawValue());
      this.visible.set(false);
      this.notification.showSuccess('Dein Konto wurde gelöscht.');
      await this.router.navigateByUrl('/account');
    } catch (failure) {
      this.error.set(
        httpErrorMessage(
          failure,
          { 403: 'Das Passwort stimmt nicht.' },
          'Löschen fehlgeschlagen. Bitte erneut versuchen.',
        ),
      );
    } finally {
      this.busy.set(false);
    }
  }

  protected reset(): void {
    this.form.reset();
    this.error.set(null);
  }
}
