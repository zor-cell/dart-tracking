import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Divider } from 'primeng/divider';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { GoogleButtonText } from '../../models/google-identity';
import { AuthService } from '../../services/auth.service';
import { GoogleButtonComponent } from '../google-button/google-button.component';

/** The way in through Google below the sign-in and registration forms. */
@Component({
  selector: 'app-google-sign-in',
  imports: [Divider, Message, GoogleButtonComponent],
  templateUrl: './google-sign-in.component.html',
  styleUrl: './google-sign-in.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GoogleSignInComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly text = input<GoogleButtonText>('signin_with');

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async signIn(credential: string): Promise<void> {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.auth.loginWithGoogle(credential);
      const redirect = this.route.snapshot.queryParamMap.get('redirect');
      await this.router.navigateByUrl(redirect ?? '/account');
    } catch (failure) {
      this.error.set(
        httpErrorMessage(
          failure,
          {
            403: $localize`:@@auth.google.unverified:Dein Google-Konto hat keine bestätigte E-Mail-Adresse.`,
            409: $localize`:@@auth.google.linkedElsewhere:Diese E-Mail-Adresse gehört zu einem Konto, das mit einem anderen Google-Konto verbunden ist.`,
          },
          $localize`:@@auth.google.failed:Anmeldung mit Google fehlgeschlagen. Bitte erneut versuchen.`,
        ),
      );
    } finally {
      this.busy.set(false);
    }
  }
}
