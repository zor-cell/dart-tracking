import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { ProgressSpinner } from 'primeng/progressspinner';

/** A spinner with what is being waited for, centred in a view. */
@Component({
  selector: 'app-loading-state',
  imports: [ProgressSpinner],
  templateUrl: './loading-state.component.html',
  styleUrl: './loading-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'loading', role: 'status' },
})
export class LoadingStateComponent {
  /** What is happening, e.g. "Spiel wird geladen"; shown with a trailing ellipsis. */
  readonly label = input.required<string>();
}
