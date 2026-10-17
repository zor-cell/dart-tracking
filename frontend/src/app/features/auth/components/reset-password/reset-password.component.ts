import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-reset-password',
  imports: [ReactiveFormsModule, RouterLink, Button, InputText, Message],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResetPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  private readonly token = inject(ActivatedRoute).snapshot.queryParamMap.get('token');

  protected readonly form = this.fb.nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
  });

  protected readonly busy = signal(false);
  protected readonly done = signal(false);
  protected readonly linkInvalid = signal(this.token === null);
  protected readonly error = signal<string | null>(null);

  protected async submit(): Promise<void> {
    if (this.token === null || this.form.invalid || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.auth.resetPassword({ token: this.token, password: this.form.getRawValue().password });
      this.done.set(true);
    } catch (failure) {
      if (failure instanceof HttpErrorResponse && failure.status === 400) {
        this.linkInvalid.set(true);
      } else {
        this.error.set('Speichern fehlgeschlagen. Bitte erneut versuchen.');
      }
    } finally {
      this.busy.set(false);
    }
  }
}
