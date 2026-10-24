import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { Button } from 'primeng/button';
import { EmptyStateComponent } from '../empty-state/empty-state.component';

/** A view whose data did not arrive: what failed, and a button to try again. */
@Component({
  selector: 'app-load-error',
  imports: [Button, EmptyStateComponent],
  templateUrl: './load-error.component.html',
  styleUrl: './load-error.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoadErrorComponent {
  /** What could not be loaded, e.g. "Das Spiel konnte nicht geladen werden." */
  readonly message = input.required<string>();
  readonly retry = output<void>();
}
