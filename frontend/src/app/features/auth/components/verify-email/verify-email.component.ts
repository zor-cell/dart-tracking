import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { Message } from 'primeng/message';
import { ProgressSpinner } from 'primeng/progressspinner';
import { AuthService } from '../../services/auth.service';

type VerifyState = 'pending' | 'verified' | 'failed';

/** Redeems a mailed link: the first confirmation of an address, or with the route
 * data `emailChange` the switch to a new one. */
@Component({
  selector: 'app-verify-email',
  imports: [RouterLink, Button, Message, ProgressSpinner],
  templateUrl: './verify-email.component.html',
  styleUrl: './verify-email.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VerifyEmailComponent {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute).snapshot;
  private readonly emailChange = this.route.data['emailChange'] === true;

  protected readonly state = signal<VerifyState>('pending');
  protected readonly isAuthenticated = this.auth.isAuthenticated;
  protected readonly verifiedText = this.emailChange
    ? 'Deine neue E-Mail-Adresse ist bestätigt und ab sofort aktiv.'
    : 'Deine E-Mail-Adresse ist bestätigt.';
  protected readonly failedText = signal(
    'Der Link ist ungültig oder abgelaufen. Einen neuen kannst du auf der Kontoseite anfordern.',
  );

  constructor() {
    void this.verify(this.route.queryParamMap.get('token'));
  }

  private async verify(token: string | null): Promise<void> {
    if (!token) {
      this.state.set('failed');
      return;
    }
    try {
      await (this.emailChange
        ? this.auth.confirmEmailChange(token)
        : this.auth.verifyEmail(token));
      this.state.set('verified');
    } catch (failure) {
      if (failure instanceof HttpErrorResponse && failure.status === 409) {
        this.failedText.set('Diese Adresse wird inzwischen von einem anderen Konto verwendet.');
      }
      this.state.set('failed');
    }
  }
}
