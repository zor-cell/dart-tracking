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
import { identityProof } from '../../models/identity-proof';
import { GoogleConfirmComponent } from '../google-confirm/google-confirm.component';

/** Deletes the signed-in account once its password is entered again. */
@Component({
  selector: 'app-delete-account-dialog',
  imports: [
    ReactiveFormsModule,
    Button,
    Dialog,
    InputText,
    Message,
    FieldErrorComponent,
    GoogleConfirmComponent,
  ],
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

  /** Accounts without a password confirm through Google; linked ones may choose it. */
  protected readonly viaGoogle = computed(() => this.auth.user()?.hasPassword === false);
  protected readonly googleCredential = signal<string | null>(null);
  protected readonly googleLinked = computed(() => this.auth.user()?.googleLinked === true);
  protected readonly useGoogle = signal(false);
  protected readonly unconfirmed = computed(
    () => this.viaGoogle() && this.googleCredential() === null,
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
    try {
      await this.auth.deleteAccount(
        identityProof(this.form.controls.currentPassword.value, this.googleCredential()),
      );
      this.visible.set(false);
      this.notification.showSuccess(
        $localize`:@@auth.deleteAccount.done:Dein Konto wurde gelöscht.`,
      );
      await this.router.navigateByUrl('/account');
    } catch (failure) {
      this.error.set(
        httpErrorMessage(
          failure,
          {
            403: () =>
              this.refused(
                $localize`:@@auth.deleteAccount.wrongPassword:Das Passwort stimmt nicht.`,
              ),
          },
          $localize`:@@auth.deleteAccount.failed:Löschen fehlgeschlagen. Bitte erneut versuchen.`,
        ),
      );
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

  /** A spent Google confirmation is dropped, so the button shows again. */
  private refused(wrongPassword: string): string {
    if (this.googleCredential() === null) {
      return wrongPassword;
    }
    this.googleCredential.set(null);
    return $localize`:@@auth.google.confirmFailed:Die Bestätigung mit Google hat nicht geklappt. Bitte erneut versuchen.`;
  }
}
