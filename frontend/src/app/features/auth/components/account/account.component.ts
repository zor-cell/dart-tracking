import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { ProgressSpinner } from 'primeng/progressspinner';
import { FitTextDirective } from '../../../../core/ui/directives/fit-text.directive';
import { APP_VERSION } from '../../../../../environments/version';
import {
  DISPLAY_NAME_MAX_LENGTH,
  USERNAME_MAX_LENGTH,
  USERNAME_MIN_LENGTH,
  USERNAME_PATTERN,
} from '../../models/profile-rules';
import { AuthService } from '../../services/auth.service';

/** The rows that can be edited in place. */
type EditableField = 'displayName' | 'username';

@Component({
  selector: 'app-account',
  imports: [
    Button,
    DatePipe,
    FitTextDirective,
    InputText,
    Message,
    ProgressSpinner,
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

  protected readonly user = this.auth.user;
  protected readonly isAdmin = this.auth.isAdmin;

  protected readonly version = APP_VERSION;

  /** The address in two parts, so the row breaks on the `@` instead of mid-word
   * when it is too long for one line. */
  protected readonly email = computed(() => {
    const address = this.user()?.email ?? '';
    const at = address.lastIndexOf('@');
    return at < 0
      ? { local: address, domain: '' }
      : { local: address.slice(0, at), domain: address.slice(at) };
  });
  protected readonly busy = signal(false);
  protected readonly restoring = signal(true);

  /** Which row is open, if any — one at a time, so the confirm button is
   * unambiguous. */
  protected readonly editingField = signal<EditableField | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

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

  protected async logout(): Promise<void> {
    this.busy.set(true);
    try {
      await this.auth.logout();
    } finally {
      this.busy.set(false);
    }
  }

  private describe(failure: unknown): string {
    if (failure instanceof HttpErrorResponse && failure.status === 409) {
      return 'Dieser Benutzername ist bereits vergeben.';
    }
    return 'Speichern fehlgeschlagen. Bitte Eingaben prüfen.';
  }
}
