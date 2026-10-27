import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  signal,
  untracked,
} from '@angular/core';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { fieldName } from '../../../game/models/field-label';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { MISS_DIRECTION_LABELS, missShares } from '../../models/miss-direction';
import { DoubleBoardComponent } from '../double-board/double-board.component';

/** Checkout figures: the rates, how far off the doubles went and each double on the board. */
@Component({
  selector: 'app-checkout-statistics',
  imports: [DecimalPipe, DoubleBoardComponent, EmptyStateComponent],
  templateUrl: './checkout-statistics.component.html',
  styleUrl: './checkout-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CheckoutStatisticsComponent {
  readonly statistics = input.required<PlayerStatisticsDto>();

  protected readonly labels = MISS_DIRECTION_LABELS;
  protected readonly selected = signal<string | null>(null);

  /** Darts that finished a leg, out of darts thrown while one dart could finish. */
  protected readonly checkoutRate = computed(() => {
    const { checkoutHits, checkoutAttempts } = this.statistics();
    return checkoutAttempts === 0 ? null : checkoutHits / checkoutAttempts;
  });

  /** Legs won out of legs that reached a finishable score at least once. */
  protected readonly legRate = computed(() => {
    const { legsWon, legsWithChance } = this.statistics();
    return legsWithChance === 0 ? null : legsWon / legsWithChance;
  });

  protected readonly selectedDouble = computed(
    () => this.statistics().doubles.find((double) => double.label === this.selected()) ?? null,
  );

  protected readonly shownName = computed(() => {
    const picked = this.selectedDouble();
    return picked ? fieldName(picked.label) : null;
  });

  private readonly directions = computed(
    () => this.selectedDouble()?.directions ?? this.statistics().missDirections,
  );
  protected readonly shares = computed(() => missShares(this.directions()));
  protected readonly directedMisses = computed(() =>
    Object.values(this.directions()).reduce((sum, count) => sum + count, 0),
  );

  constructor() {
    // New figures drop a pick that is no longer among their doubles.
    effect(() => {
      const doubles = this.statistics().doubles;
      untracked(() => {
        if (!doubles.some((double) => double.label === this.selected())) {
          this.selected.set(null);
        }
      });
    });
  }
}
