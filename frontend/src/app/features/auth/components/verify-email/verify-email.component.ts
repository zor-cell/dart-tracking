import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { AuthService } from '../../services/auth.service';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** `failed`: the link itself is invalid; `error`: the server could not be asked;
 * `taken`: the address now belongs to another account; `resent`: a new link is on its way. */
type VerifyState = 'pending' | 'verified' | 'failed' | 'error' | 'taken' | 'resent';

/** Redeems a mailed link: the first confirmation of an address, or with the route
 * data `emailChange` the switch to a new one. */
@Component({
  selector: 'app-verify-email',
  imports: [
    Button,
    EmptyStateComponent,
    LoadErrorComponent,
    LoadingStateComponent,
    Message,
    RouterLink,
  ],
  templateUrl: './verify-email.component.html',
  styleUrl: './verify-email.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VerifyEmailComponent {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute).snapshot;
  private readonly emailChange = this.route.data['emailChange'] === true;
  private readonly token = this.route.queryParamMap.get('token');

  protected readonly state = signal<VerifyState>('pending');
  protected readonly errorMessage = signal('');
  protected readonly isAuthenticated = this.auth.isAuthenticated;
  protected readonly verifiedText = this.emailChange
    ? 'Deine neue E-Mail-Adresse ist bestätigt und ab sofort aktiv.'
    : 'Deine E-Mail-Adresse ist bestätigt.';
  protected readonly resending = signal(false);
  protected readonly resendError = signal<string | null>(null);

  /** Only a first confirmation can be resent, and only to its signed-in, unconfirmed owner. */
  protected readonly canResend = computed(
    () => !this.emailChange && this.auth.user()?.emailVerified === false,
  );

  constructor() {
    void this.verify();
  }

  protected async verify(): Promise<void> {
    const token = this.token;
    if (!token) {
      this.state.set('failed');
      return;
    }
    this.state.set('pending');
    try {
      await (this.emailChange
        ? this.auth.confirmEmailChange(token)
        : this.auth.verifyEmail(token));
      this.state.set('verified');
    } catch (failure) {
      const status = failure instanceof HttpErrorResponse ? failure.status : null;
      if (status === 400) {
        this.state.set('failed');
      } else if (status === 409) {
        this.state.set('taken');
      } else {
        this.errorMessage.set(
          httpErrorMessage(failure, {}, 'Die Adresse konnte gerade nicht bestätigt werden.'),
        );
        this.state.set('error');
      }
    }
  }

  protected async resend(): Promise<void> {
    if (this.resending()) {
      return;
    }
    this.resending.set(true);
    this.resendError.set(null);
    try {
      await this.auth.resendVerification();
      this.state.set('resent');
    } catch (failure) {
      this.resendError.set(
        httpErrorMessage(failure, {}, 'Senden fehlgeschlagen. Bitte später erneut versuchen.'),
      );
    } finally {
      this.resending.set(false);
    }
  }
}
