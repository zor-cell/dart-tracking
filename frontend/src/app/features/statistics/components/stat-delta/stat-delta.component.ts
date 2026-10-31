import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

type Verdict = 'better' | 'worse' | 'even';

/** The compared player's value under a figure, and how far one's own lies above or below it. */
@Component({
  selector: 'app-stat-delta',
  imports: [DecimalPipe],
  templateUrl: './stat-delta.component.html',
  styleUrl: './stat-delta.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatDeltaComponent {
  readonly own = input.required<number | null>();
  readonly other = input.required<number | null>();
  readonly name = input.required<string>();
  /** Decimals both values are shown with. */
  readonly digits = input(1);
  /** Written after the other value only; the difference beside it shares it. */
  readonly unit = input('');
  /** Where less is better, such as a distance; turns the colours round. */
  readonly lowerIsBetter = input(false);
  /** Only the other value, without a difference, for figures that are no better or worse. */
  readonly neutral = input(false);

  protected readonly format = computed(() => `1.${this.digits()}-${this.digits()}`);

  /** One's own value minus the other's, rounded as shown; null where either is missing. */
  protected readonly difference = computed(() => {
    const own = this.own();
    const other = this.other();
    if (this.neutral() || own === null || other === null) {
      return null;
    }
    const scale = 10 ** this.digits();
    return Math.round((own - other) * scale) / scale;
  });

  protected readonly verdict = computed<Verdict | null>(() => {
    const difference = this.difference();
    if (difference === null) {
      return null;
    }
    if (difference === 0) {
      return 'even';
    }
    return difference > 0 !== this.lowerIsBetter() ? 'better' : 'worse';
  });
}
