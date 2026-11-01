import { ChangeDetectionStrategy, Component } from '@angular/core';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { OPERATOR } from '../../models/operator';

/** The disclosure Austrian media law asks of every website. */
@Component({
  selector: 'app-imprint',
  imports: [BackLinkComponent],
  templateUrl: './imprint.component.html',
  styleUrl: './imprint.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ImprintComponent {
  protected readonly operator = OPERATOR;
}
