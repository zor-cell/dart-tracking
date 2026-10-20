import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { StatisticsService } from '../../services/statistics.service';
import { TipHeatmapComponent } from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { BackLinkComponent } from '../../../../core/view/components/back-link/back-link.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';

@Component({
  selector: 'app-statistics',
  imports: [
    BackLinkComponent,
    DecimalPipe,
    LoadingStateComponent,
    EmptyStateComponent,
    TipHeatmapComponent,
  ],
  templateUrl: './statistics.component.html',
  styleUrl: './statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatisticsComponent {
  private readonly statistics = inject(StatisticsService);

  protected readonly totals = signal<PlayerStatisticsDto | null>(null);
  protected readonly loading = signal(true);

  /** Darts that finished a leg, out of darts thrown while one dart could finish. */
  protected readonly checkoutRate = computed(() => {
    const totals = this.totals();
    return !totals || totals.checkoutAttempts === 0
      ? null
      : totals.checkoutHits / totals.checkoutAttempts;
  });

  /** Legs won out of legs that reached a finishable score at least once. */
  protected readonly legRate = computed(() => {
    const totals = this.totals();
    return !totals || totals.legsWithChance === 0 ? null : totals.legsWon / totals.legsWithChance;
  });

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      this.totals.set(await this.statistics.load());
    } finally {
      this.loading.set(false);
    }
  }
}
