import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { LoadingStateComponent } from '../loading-state/loading-state.component';

/** Content that is fetched again: kept in place, swapped for a bare spinner while a reload takes long. */
@Component({
  selector: 'app-reloading',
  imports: [LoadingStateComponent],
  templateUrl: './reloading.component.html',
  styleUrl: './reloading.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'reloading',
    '[class.reloading--busy]': 'busy()',
    '[attr.aria-busy]': 'busy()',
  },
})
export class ReloadingComponent {
  readonly busy = input.required<boolean>();
  /** What is being fetched, for screen readers only. */
  readonly label = input.required<string>();
}
