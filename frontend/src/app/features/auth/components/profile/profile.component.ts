import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Button } from 'primeng/button';
import { Popover } from 'primeng/popover';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import {
  DISPLAY_NAME_MAX_LENGTH,
  USERNAME_MAX_LENGTH,
  USERNAME_MESSAGES,
  USERNAME_MIN_LENGTH,
  USERNAME_PATTERN,
} from '../../models/profile-rules';
import { AuthService } from '../../services/auth.service';
import { ChangeEmailDialogComponent } from '../change-email-dialog/change-email-dialog.component';
import { ChangePasswordDialogComponent } from '../change-password-dialog/change-password-dialog.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { centrePopoverArrow } from '../../../../core/view/models/popover-arrow';
import { InlineEditorComponent } from '../../../../core/view/components/inline-editor/inline-editor.component';

/** The rows that can be edited in place. */
type EditableField = 'displayName' | 'username';

interface EditableRow {
  readonly field: EditableField;
  readonly label: string;
  readonly autocomplete: string;
  readonly messages: Readonly<Record<string, string>>;
}

/** The signed-in account's names, sign-in details and the way out of the session. */
@Component({
  selector: 'app-profile',
  imports: [
    BackLinkComponent,
    Button,
    ChangeEmailDialogComponent,
    ChangePasswordDialogComponent,
    InlineEditorComponent,
    Popover,
  ],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent {
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  protected readonly user = this.auth.user;

  protected readonly busy = signal(false);

  /** Which row is open, if any — one at a time, so the confirm button is
   * unambiguous. */
  protected readonly editingField = signal<EditableField | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly resending = signal(false);
  protected readonly verificationSent = signal(false);
  private readonly resendError = signal<string | null>(null);
  protected readonly emailDialogOpen = signal(false);
  protected readonly passwordDialogOpen = signal(false);
  protected readonly emailStatus = computed(() =>
    this.user()?.emailVerified ? 'E-Mail-Adresse bestätigt' : 'E-Mail-Adresse nicht bestätigt',
  );
  protected readonly verifyNotice = computed(() => {
    if (this.user()?.emailVerified) {
      return 'Deine E-Mail-Adresse ist bestätigt.';
    }
    return (
      this.resendError() ??
      (this.verificationSent()
        ? 'Ein neuer Bestätigungslink ist unterwegs. Er ist 24 Stunden gültig.'
        : 'Deine E-Mail-Adresse ist noch nicht bestätigt. Den Link dazu findest du in deinem Postfach.')
    );
  });

  protected readonly editableRows: readonly EditableRow[] = [
    { field: 'displayName', label: 'Anzeigename', autocomplete: 'nickname', messages: {} },
    { field: 'username', label: 'Benutzername', autocomplete: 'username', messages: USERNAME_MESSAGES },
  ];

  /** Both names, because the write sends both; only the open one is shown as an
   * input, the other rides along unchanged. */
  protected readonly form = this.fb.nonNullable.group({
    displayName: ['', [Validators.required, Validators.maxLength(DISPLAY_NAME_MAX_LENGTH)]],
    username: [
      '',
      [
        Validators.required,
        Validators.minLength(USERNAME_MIN_LENGTH),
        Validators.maxLength(USERNAME_MAX_LENGTH),
        Validators.pattern(USERNAME_PATTERN),
      ],
    ],
  });

  /** Seeded from the session on every open, so a cancelled edit leaves nothing
   * behind and a rename by another device is picked up. */
  protected edit(field: EditableField): void {
    const account = this.user();
    if (!account) {
      return;
    }
    this.form.setValue({ displayName: account.displayName, username: account.username });
    this.error.set(null);
    this.editingField.set(field);
  }

  protected cancel(): void {
    this.editingField.set(null);
    this.error.set(null);
  }

  protected async confirm(): Promise<void> {
    const field = this.editingField();
    if (field === null || this.form.controls[field].invalid || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    try {
      await this.auth.updateProfile(this.form.getRawValue());
      this.editingField.set(null);
    } catch (failure) {
      this.error.set(this.describe(failure));
    } finally {
      this.saving.set(false);
    }
  }

  protected async resendVerification(): Promise<void> {
    if (this.resending()) {
      return;
    }
    this.resending.set(true);
    this.resendError.set(null);
    try {
      await this.auth.resendVerification();
      this.verificationSent.set(true);
    } catch (failure) {
      this.resendError.set(
        httpErrorMessage(failure, {}, 'Senden fehlgeschlagen. Bitte später erneut versuchen.'),
      );
    } finally {
      this.resending.set(false);
    }
  }

  protected readonly centerArrow = centrePopoverArrow;

  protected async logout(): Promise<void> {
    this.busy.set(true);
    try {
      await this.auth.logout();
      await this.router.navigateByUrl('/account');
    } finally {
      this.busy.set(false);
    }
  }

  private describe(failure: unknown): string {
    return httpErrorMessage(
      failure,
      {
        409: (error) =>
          error.error?.detail === 'display name in address book'
            ? 'Diesen Namen gibt es schon in deiner Spielerliste.'
            : 'Dieser Benutzername ist bereits vergeben.',
      },
      'Speichern fehlgeschlagen. Bitte Eingaben prüfen.',
    );
  }
}
