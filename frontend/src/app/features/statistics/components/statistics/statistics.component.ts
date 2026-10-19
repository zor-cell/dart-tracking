import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { StatisticsService } from '../../services/statistics.service';
import { BoardHeatmapComponent } from '../board-heatmap/board-heatmap.component';

@Component({
  selector: 'app-statistics',
  imports: [Button, BoardHeatmapComponent, DecimalPipe, ProgressSpinner, RouterLink],
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
