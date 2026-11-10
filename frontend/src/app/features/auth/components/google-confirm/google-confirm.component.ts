import { ChangeDetectionStrategy, Component, input, model, output } from '@angular/core';
import { GoogleButtonComponent } from '../google-button/google-button.component';

/** Confirms a sensitive change by signing in with Google again, alone or as the alternative to a password. */
@Component({
  selector: 'app-google-confirm',
  imports: [GoogleButtonComponent],
  templateUrl: './google-confirm.component.html',
  styleUrl: './google-confirm.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GoogleConfirmComponent {
  readonly credential = model<string | null>(null);
  readonly alternative = input(false);
  readonly back = output<void>();
}
