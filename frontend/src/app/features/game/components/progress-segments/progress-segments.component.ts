import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { ProgressBar } from 'primeng/progressbar';
import { ProgressSegment } from '../../models/progress-segment';

/** A thin bar split into segments, each filling on its own. */
@Component({
  selector: 'app-progress-segments',
  imports: [ProgressBar],
  templateUrl: './progress-segments.component.html',
  styleUrl: './progress-segments.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProgressSegmentsComponent {
  readonly segments = input.required<readonly ProgressSegment[]>();

  protected readonly tokens = { height: '4px', borderRadius: '0' };
}
