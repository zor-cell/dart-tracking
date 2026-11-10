import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  model,
  signal,
} from '@angular/core';
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
import { identityProof } from '../../models/identity-proof';
import { GoogleConfirmComponent } from '../google-confirm/google-confirm.component';

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
    GoogleConfirmComponent,
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

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  /** Accounts without a password confirm through Google; linked ones may choose it. */
  protected readonly viaGoogle = computed(() => this.auth.user()?.hasPassword === false);
  protected readonly googleCredential = signal<string | null>(null);
  protected readonly googleLinked = computed(() => this.auth.user()?.googleLinked === true);
  protected readonly useGoogle = signal(false);
  protected readonly unconfirmed = computed(
    () => this.viaGoogle() && this.googleCredential() === null,
  );
  protected readonly title = computed(() =>
    this.viaGoogle()
      ? $localize`:@@auth.setPassword:Passwort festlegen`
      : $localize`:@@auth.changePassword:Passwort ändern`,
  );

  constructor() {
    effect(() => {
      const password = this.form.controls.currentPassword;
      if (this.viaGoogle() || this.googleCredential() !== null) {
        password.disable();
      } else {
        password.enable();
      }
    });
  }

  protected async submit(): Promise<void> {
    if (this.form.invalid || this.busy() || this.unconfirmed()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    const setting = this.viaGoogle();
    try {
      const { currentPassword, newPassword } = this.form.getRawValue();
      await this.auth.changePassword({
        newPassword,
        ...identityProof(currentPassword, this.googleCredential()),
      });
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
    this.googleCredential.set(null);
    this.useGoogle.set(false);
  }

  protected useGoogleInstead(): void {
    this.form.controls.currentPassword.reset();
    this.useGoogle.set(true);
  }

  protected usePassword(): void {
    this.form.controls.currentPassword.reset();
    this.useGoogle.set(false);
    this.googleCredential.set(null);
  }

  private describe(failure: unknown): string {
    return httpErrorMessage(
      failure,
      {
        403: () =>
          this.refused($localize`:@@auth.currentPasswordWrong:Das aktuelle Passwort stimmt nicht.`),
      },
      $localize`:@@auth.saveFailed:Speichern fehlgeschlagen. Bitte erneut versuchen.`,
    );
  }

  /** A spent Google confirmation is dropped, so the button shows again. */
  private refused(wrongPassword: string): string {
    if (this.googleCredential() === null) {
      return wrongPassword;
    }
    this.googleCredential.set(null);
    return $localize`:@@auth.google.confirmFailed:Die Bestätigung mit Google hat nicht geklappt. Bitte erneut versuchen.`;
  }
}
