import { computed, effect, inject, signal } from '@angular/core';
import { FormControl } from '@angular/forms';
import { IdentityConfirmationDto } from '../dto/identity-confirmation.dto';
import { AuthService } from '../services/auth.service';

/** Proves the account again before a sensitive change, by its password or through Google.
 * Create it in an injection context, such as a component's field. */
export class IdentityCheck {
  private readonly auth = inject(AuthService);

  /** Accounts without a password confirm through Google; linked ones may choose it. */
  readonly viaGoogle = computed(() => this.auth.user()?.hasPassword === false);
  readonly googleLinked = computed(() => this.auth.user()?.googleLinked === true);
  readonly credential = signal<string | null>(null);
  readonly useGoogle = signal(false);
  readonly unconfirmed = computed(() => this.viaGoogle() && this.credential() === null);

  constructor(readonly password: FormControl<string>) {
    effect(() => {
      if (this.viaGoogle() || this.credential() !== null) {
        password.disable();
      } else {
        password.enable();
      }
    });
  }

  /** The Google token once one was given, else the typed password. */
  proof(): IdentityConfirmationDto {
    const googleCredential = this.credential();
    return googleCredential !== null
      ? { googleCredential }
      : { currentPassword: this.password.value };
  }

  reset(): void {
    this.credential.set(null);
    this.useGoogle.set(false);
  }

  useGoogleInstead(): void {
    this.password.reset();
    this.useGoogle.set(true);
  }

  usePassword(): void {
    this.password.reset();
    this.useGoogle.set(false);
    this.credential.set(null);
  }

  /** The message for a refused proof; a spent Google confirmation is dropped, so the
   * button shows again. */
  refused(wrongPassword: string): string {
    if (this.credential() === null) {
      return wrongPassword;
    }
    this.credential.set(null);
    return $localize`:@@auth.google.confirmFailed:Die Bestätigung mit Google hat nicht geklappt. Bitte erneut versuchen.`;
  }
}
