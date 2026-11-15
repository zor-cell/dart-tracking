import { ChangeDetectionStrategy, Component, computed, inject, model, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Button } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { InputText } from 'primeng/inputtext';
import { AutoFocus } from 'primeng/autofocus';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { NotificationService } from '../../../../core/notification/services/notification.service';
import { AuthService } from '../../services/auth.service';
import { FieldErrorComponent } from '../../../../core/view/components/field-error/field-error.component';
import { DIALOG_STYLE } from '../../../../core/view/models/dialog-style';
import { IdentityCheck } from '../../models/identity-check';
import { IdentityProofComponent } from '../identity-proof/identity-proof.component';

@Component({
  selector: 'app-change-password-dialog',
  imports: [
    ReactiveFormsModule,
    AutoFocus,
    Button,
    Dialog,
    InputText,
    Message,
    FieldErrorComponent,
    IdentityProofComponent,
  ],
  templateUrl: './change-password-dialog.component.html',
  styleUrl: './change-password-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChangePasswordDialogComponent {
  protected readonly dialogStyle = DIALOG_STYLE;
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly notification = inject(NotificationService);

  readonly visible = model(false);

  protected readonly form = this.fb.nonNullable.group({
    currentPassword: ['', [Validators.required, Validators.maxLength(128)]],
    newPassword: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
  });

  protected readonly identity = new IdentityCheck(this.form.controls.currentPassword);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly title = computed(() =>
    this.identity.viaGoogle()
      ? $localize`:@@auth.setPassword:Passwort festlegen`
      : $localize`:@@auth.changePassword:Passwort ändern`,
  );

  protected async submit(): Promise<void> {
    if (this.form.invalid || this.busy() || this.identity.unconfirmed()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    const setting = this.identity.viaGoogle();
    try {
      const { newPassword } = this.form.getRawValue();
      await this.auth.changePassword({ newPassword, ...this.identity.proof() });
      this.notification.showSuccess(
        setting
          ? $localize`:@@auth.setPassword.done:Passwort festgelegt. Andere Geräte wurden abgemeldet.`
          : $localize`:@@auth.changePassword.done:Passwort geändert. Andere Geräte wurden abgemeldet.`,
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
    this.identity.reset();
  }

  private describe(failure: unknown): string {
    return httpErrorMessage(
      failure,
      {
        403: () =>
          this.identity.refused(
            $localize`:@@auth.currentPasswordWrong:Das aktuelle Passwort stimmt nicht.`,
          ),
      },
      $localize`:@@auth.saveFailed:Speichern fehlgeschlagen. Bitte erneut versuchen.`,
    );
  }
}
