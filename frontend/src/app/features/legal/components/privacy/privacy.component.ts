import { ChangeDetectionStrategy, Component } from '@angular/core';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { OPERATOR } from '../../models/operator';

/** What the app stores about whom, and why. */
@Component({
  selector: 'app-privacy',
  imports: [BackLinkComponent],
  templateUrl: './privacy.component.html',
  styleUrl: './privacy.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrivacyComponent {
  protected readonly operator = OPERATOR;
}
