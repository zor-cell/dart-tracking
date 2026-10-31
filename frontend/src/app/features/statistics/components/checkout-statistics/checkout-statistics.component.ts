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
import { RouterLink } from '@angular/router';
import { DistanceScaleComponent } from '../../../game/components/distance-scale/distance-scale.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { backState } from '../../../../core/view/models/back-state';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { DoubleBoardComponent } from '../double-board/double-board.component';
import { StatSketchComponent } from '../stat-sketch/stat-sketch.component';

/** Checkout figures: the rates, how far off the doubles went and each double on the board. */
@Component({
  selector: 'app-checkout-statistics',
  imports: [
    DecimalPipe,
    DistanceScaleComponent,
    DoubleBoardComponent,
    EmptyStateComponent,
    InfoHintComponent,
    RouterLink,
    StatSketchComponent,
  ],
  templateUrl: './checkout-statistics.component.html',
  styleUrl: './checkout-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CheckoutStatisticsComponent {
  readonly statistics = input.required<PlayerStatisticsDto>();
  /** Brings the views the cards open back here. */
  protected readonly returnState = backState('Statistik');

  protected readonly selected = signal<string | null>(null);

  /** Darts that finished a leg, out of darts thrown while one dart could finish. */
  protected readonly checkoutRate = computed(() => {
    const { checkoutHits, checkoutAttempts } = this.statistics();
    return checkoutAttempts === 0 ? null : checkoutHits / checkoutAttempts;
  });

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
