import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';

/** One series of a trend chart as its legend shows it. */
export interface TrendLegendEntry {
  readonly key: string;
  readonly label: string;
  /** Single games as dots, a line through them, a dashed line, or bars. */
  readonly swatch: 'dot' | 'line' | 'dash' | 'box';
  /** Colour of the swatch; the muted text colour without one. */
  readonly color?: string;
  /** What the series means, behind an info button. */
  readonly hint?: string;
}

/** The legend of a trend chart: every series a switch that hides or shows it. Projects further
 * entries that switch nothing, such as the gap marker of a comparison. */
@Component({
  selector: 'app-trend-legend',
  imports: [InfoHintComponent],
  templateUrl: './trend-legend.component.html',
  styleUrl: './trend-legend.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrendLegendComponent {
  readonly entries = input.required<readonly TrendLegendEntry[]>();
  readonly hidden = input.required<ReadonlySet<string>>();
  readonly toggle = output<string>();
}
