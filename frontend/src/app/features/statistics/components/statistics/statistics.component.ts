import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { ProgressSpinner } from 'primeng/progressspinner';
import { GameSummaryDto, GameStatus } from '../../../game/dto/game-summary.dto';
import { GameHistoryService } from '../../../game/services/game-history.service';
import { PlayerStatisticsDto } from '../../dto/player-statistics.dto';
import { StatisticsService } from '../../services/statistics.service';
import { BoardHeatmapComponent } from '../board-heatmap/board-heatmap.component';

/** How many games one page of the history holds. */
const PAGE_SIZE = 10;

const STATUS_LABELS: Record<GameStatus, string> = {
  active: 'läuft',
  finished: 'beendet',
  abandoned: 'abgebrochen',
  discarded: 'verworfen',
};

@Component({
  selector: 'app-statistics',
  imports: [Button, BoardHeatmapComponent, DatePipe, DecimalPipe, ProgressSpinner, RouterLink],
  templateUrl: './statistics.component.html',
  styleUrl: './statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatisticsComponent {
  private readonly statistics = inject(StatisticsService);
  private readonly history = inject(GameHistoryService);

  protected readonly totals = signal<PlayerStatisticsDto | null>(null);
  protected readonly games = signal<GameSummaryDto[]>([]);
  /** The first load only: a later refresh keeps the page and reports itself on
   * the row that triggered it. */
  protected readonly loading = signal(true);
  protected readonly moreAvailable = signal(false);
  protected readonly busyGameId = signal<string | null>(null);

  protected readonly statusLabels = STATUS_LABELS;

  /** Legs won out of legs that reached a finishable score at least once. */
  protected readonly checkoutRate = computed(() => {
    const totals = this.totals();
    return !totals || totals.checkoutChances === 0 ? null : totals.legsWon / totals.checkoutChances;
  });

  /** Darts that finished a leg, out of darts thrown while on a double. */
  protected readonly doubleRate = computed(() => {
    const totals = this.totals();
    return !totals || totals.doubleAttempts === 0
      ? null
      : totals.doubleHits / totals.doubleAttempts;
  });

  constructor() {
    void this.reload();
  }

  protected async loadMore(): Promise<void> {
    const page = await this.history.list(PAGE_SIZE, this.games().length);
    this.games.update((games) => [...games, ...page]);
    this.moreAvailable.set(page.length === PAGE_SIZE);
  }

  /** Toggling a game changes the totals, so both are fetched again. */
  protected async toggleCounted(game: GameSummaryDto): Promise<void> {
    this.busyGameId.set(game.id);
    try {
      await this.history.setCounted(game.id, !game.counted);
      await this.reload();
    } finally {
      this.busyGameId.set(null);
    }
  }

  private async reload(): Promise<void> {
    try {
      const [totals, page] = await Promise.all([
        this.statistics.load(),
        this.history.list(PAGE_SIZE, 0),
      ]);
      this.totals.set(totals);
      this.games.set(page);
      this.moreAvailable.set(page.length === PAGE_SIZE);
    } finally {
      this.loading.set(false);
    }
  }
}
