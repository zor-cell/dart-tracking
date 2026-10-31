import { formatNumber } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
} from '@angular/core';
import { Popover } from 'primeng/popover';
import { centrePopoverArrow } from '../../../../core/view/models/popover-arrow';

type Verdict = 'better' | 'worse' | 'even';

const SYMBOLS: Record<Verdict, string> = { better: '▲', worse: '▼', even: '=' };

/** Beside one's own figure: up, down or level against the compared player, green where that is
 * better and red where it is worse; a tap tells by how much. */
@Component({
  selector: 'app-delta-mark',
  imports: [Popover],
  templateUrl: './delta-mark.component.html',
  styleUrl: './delta-mark.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DeltaMarkComponent {
  private readonly locale = inject(LOCALE_ID);

  readonly own = input.required<number | null>();
  readonly other = input.required<number | null>();
  readonly name = input.required<string>();
  /** Decimals the difference is told with, as the figures are shown. */
  readonly digits = input(1);
  readonly unit = input('');
  /** Where less is better, such as a distance; turns the colours round. */
  readonly lowerIsBetter = input(false);

  /** One's own value minus the other's, rounded as shown; null where either is missing. */
  private readonly difference = computed(() => {
    const own = this.own();
    const other = this.other();
    if (own === null || other === null) {
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

  protected readonly symbol = computed(() => {
    const verdict = this.verdict();
    return verdict === null ? '' : SYMBOLS[verdict];
  });

  /** The difference in words, e.g. "17.7 weniger als Flo". */
  protected readonly detail = computed(() => {
    const difference = this.difference();
    if (difference === null) {
      return '';
    }
    if (difference === 0) {
      return `Gleich wie ${this.name()}`;
    }
    const digits = this.digits();
    const amount = formatNumber(Math.abs(difference), this.locale, `1.${digits}-${digits}`);
    return `${amount}${this.unit()} ${difference > 0 ? 'mehr' : 'weniger'} als ${this.name()}`;
  });

  protected place(popover: Popover): void {
    centrePopoverArrow(popover);
  }
}
