import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { httpErrorMessage } from '../../../../core/notification/models/http-error-message';
import { AuthService } from '../../services/auth.service';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';

@Component({
  selector: 'app-forgot-password',
  imports: [BackLinkComponent, Button, InputText, Message, ReactiveFormsModule],
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  protected readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  protected readonly busy = signal(false);
  protected readonly sent = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async submit(): Promise<void> {
    if (this.form.invalid || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.auth.requestPasswordReset(this.form.getRawValue());
      this.sent.set(true);
    } catch (failure) {
      this.error.set(
        httpErrorMessage(failure, {}, 'Anfrage fehlgeschlagen. Bitte später erneut versuchen.'),
      );
    } finally {
      this.busy.set(false);
    }
  }
}
