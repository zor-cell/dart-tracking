import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Popover } from 'primeng/popover';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { APP_VERSION } from '../../../../../environments/version';
import {
  DISPLAY_NAME_MAX_LENGTH,
  USERNAME_MAX_LENGTH,
  USERNAME_MIN_LENGTH,
  USERNAME_PATTERN,
} from '../../models/profile-rules';
import { AuthService } from '../../services/auth.service';
import { ChangeEmailDialogComponent } from '../change-email-dialog/change-email-dialog.component';
import { ChangePasswordDialogComponent } from '../change-password-dialog/change-password-dialog.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** The rows that can be edited in place. */
type EditableField = 'displayName' | 'username';

@Component({
  selector: 'app-account',
  imports: [
    Button,
    ChangeEmailDialogComponent,
    ChangePasswordDialogComponent,
    InputText,
    LoadingStateComponent,
    Message,
    Popover,
    ReactiveFormsModule,
    RouterLink,
  ],
  templateUrl: './account.component.html',
  styleUrl: './account.component.scss',
  // Presses outside the open row close it. Bound to `pointerdown` rather than
  // `click` because it runs before focus moves and before the button's own
  // handler, so pressing another row's pencil closes this row and then opens
  // that one, in that order.
  host: { '(document:pointerdown)': 'onPointerDown($event)' },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccountComponent {
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly document = inject(DOCUMENT);

  protected readonly user = this.auth.user;
  protected readonly isAdmin = this.auth.isAdmin;

  protected readonly version = APP_VERSION;

  protected readonly busy = signal(false);
  protected readonly restoring = signal(true);

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

  constructor() {
    // This page is what it shows: everything on it hangs off `user()`, and
    // nothing else on this route asks for the session to be restored first.
    void this.auth.ready.then(() => this.restoring.set(false));
  }

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

  protected onPointerDown(event: Event): void {
    if (this.editingField() === null) {
      return;
    }
    const target = event.target as Element | null;
    if (target?.closest('.account__row--editing')) {
      return;
    }
    this.cancel();
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

  /** Points the arrow at the button's center, measured on the layout box since
   * PrimeNG aligns it while the opening animation still scales the popover. */
  protected centerArrow(popover: Popover): void {
    const container = popover.container;
    const target = popover.target as HTMLElement | null;
    if (!container || !target) {
      return;
    }
    const rect = target.getBoundingClientRect();
    const scrollX = this.document.defaultView?.scrollX ?? 0;
    const center = rect.left + scrollX + rect.width / 2 - container.offsetLeft;
    container.style.setProperty(
      '--p-popover-arrow-left',
      `calc(${center}px - var(--p-popover-arrow-offset))`,
    );
  }

  protected async logout(): Promise<void> {
    this.busy.set(true);
    try {
      await this.auth.logout();
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
