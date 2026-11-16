import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { ProgressBar } from 'primeng/progressbar';
import { ProgressSegment } from '../../models/progress-segment';

/** A thin bar split into segments, each filling on its own, with an optional label on it. */
@Component({
  selector: 'app-progress-segments',
  imports: [ProgressBar],
  templateUrl: './progress-segments.component.html',
  styleUrl: './progress-segments.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProgressSegmentsComponent {
  readonly segments = input.required<readonly ProgressSegment[]>();
  readonly label = input<string | null>(null);

  protected readonly tokens = { height: '4px', borderRadius: '0' };
}
