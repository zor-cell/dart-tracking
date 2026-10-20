import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** A view's empty or failed state: an optional icon above whatever is projected. */
@Component({
  selector: 'app-empty-state',
  templateUrl: './empty-state.component.html',
  styleUrl: './empty-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'empty-state' },
})
export class EmptyStateComponent {
  /** A PrimeIcons class such as `pi-video`. */
  readonly icon = input<string | null>(null);
}
