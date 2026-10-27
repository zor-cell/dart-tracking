import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, signal } from '@angular/core';
import {
  HeatBoardComponent,
  HeatField,
} from '../../../game/components/heat-board/heat-board.component';
import { fieldName } from '../../../game/models/field-label';
import { DoubleStatisticsDto } from '../../dto/double-statistics.dto';

/** Fill opacity of a double never hit and of the best hit one. */
const MIN_OPACITY = 0.2;
const MAX_OPACITY = 0.9;

/** The finishing doubles on the board, tinted by how often they were hit; a tap picks one. */
@Component({
  selector: 'app-double-board',
  imports: [DecimalPipe, HeatBoardComponent],
  templateUrl: './double-board.component.html',
  styleUrl: './double-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DoubleBoardComponent {
  readonly doubles = input.required<readonly DoubleStatisticsDto[]>();
  /** Label of the picked double. */
  readonly selected = model<string | null>(null);

  protected readonly hovered = signal<string | null>(null);

  protected readonly scale = (share: number): number =>
    MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * share;

  protected readonly selectable = (label: string): boolean =>
    this.doubles().some((double) => double.label === label);

  private readonly best = computed(() =>
    Math.max(0, ...this.doubles().map((double) => double.hits / double.attempts)),
  );

  protected readonly attempts = computed(() =>
    this.doubles().reduce((sum, double) => sum + double.attempts, 0),
  );

  protected readonly fields = computed<HeatField[]>(() =>
    this.doubles().map((double) => ({
      label: double.label,
      share: this.best() === 0 ? 0 : double.hits / double.attempts / this.best(),
      ariaLabel: `${fieldName(double.label)}: ${double.hits} von ${double.attempts} getroffen`,
    })),
  );

  protected readonly legendMax = computed(() => `${Math.round(this.best() * 100)} %`);

  /** The double under the pointer or picked, with its rate. */
  protected readonly shown = computed(() => {
    const label = this.hovered() ?? this.selected();
    const double = this.doubles().find((entry) => entry.label === label);
    return double
      ? { ...double, name: fieldName(double.label), rate: double.hits / double.attempts }
      : null;
  });
}
