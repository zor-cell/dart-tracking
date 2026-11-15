import { DOCUMENT, DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import type { ChartData, ChartOptions } from 'chart.js';
import { Button } from 'primeng/button';
import { UIChart } from 'primeng/chart';
import { AuthService } from '../../../auth/services/auth.service';
import { GameSummaryDto } from '../../../game/dto/game-summary.dto';
import { gameTitle } from '../../../game/models/game-settings';
import { GameHistoryService } from '../../../game/services/game-history.service';
import { DeltaMarkComponent } from '../../../statistics/components/delta-mark/delta-mark.component';
import { StatLinkComponent } from '../../../statistics/components/stat-link/stat-link.component';
import { StatisticsOverviewDto } from '../../../statistics/dto/statistics-overview.dto';
import { OWN_COLOR } from '../../../statistics/models/comparison';
import { StatisticsFilter } from '../../../statistics/models/statistics-filter';
import { StatisticsService } from '../../../statistics/services/statistics.service';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { chartBase } from '../../../../core/charts/models/chart-styles';
import { SHORT_DATE } from '../../../../core/i18n/models/date-format';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';
import { periodStart } from '../../../../core/view/models/period';

/** Days the overview covers, and the same span before it that the deltas compare with. */
const DAYS = 30;

interface Overview {
  readonly recent: StatisticsOverviewDto;
  readonly previous: StatisticsOverviewDto;
  readonly lastGame: GameSummaryDto | null;
}

function x01Filter(since: Date | null, until: Date | null): StatisticsFilter {
  return {
    variants: ['x01'],
    modes: [],
    checkoutModes: [],
    killerZones: [],
    cricketScorings: [],
    clockZones: [],
    trainingGoals: [],
    trainingRings: [],
    opponentIds: [],
    playerCounts: [],
    since,
    until,
    lastGames: null,
  };
}

function checkoutRate(statistics: StatisticsOverviewDto): number | null {
  return statistics.checkoutAttempts === 0
    ? null
    : (100 * statistics.checkoutHits) / statistics.checkoutAttempts;
}

/** The home page: the account's recent x01 form, or what the app does for a guest. */
@Component({
  selector: 'app-start',
  imports: [
    Button,
    DatePipe,
    DecimalPipe,
    DeltaMarkComponent,
    EmptyStateComponent,
    LoadErrorComponent,
    LoadingStateComponent,
    NgTemplateOutlet,
    RouterLink,
    StatLinkComponent,
    UIChart,
  ],
  templateUrl: './start.component.html',
  styleUrl: './start.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StartComponent {
  private readonly auth = inject(AuthService);
  private readonly statistics = inject(StatisticsService);
  private readonly history = inject(GameHistoryService);
  private readonly theme = chartTheme(inject(DOCUMENT));

  protected readonly user = this.auth.user;
  protected readonly restoring = signal(true);
  protected readonly overview = signal<Overview | null>(null);
  protected readonly loading = signal(false);
  protected readonly failed = signal(false);

  protected readonly shortDate = SHORT_DATE;
  protected readonly back = $localize`:@@common.nav.start:Start`;
  protected readonly statsParams = { game: 'x01', period: 'days30' };
  protected readonly before = $localize`:@@start.before:in den 30 Tagen davor`;

  /** Whether the account has no game yet, so the page explains how to start instead. */
  protected readonly fresh = computed(() => {
    const overview = this.overview();
    return overview !== null && overview.lastGame === null;
  });

  protected readonly checkout = computed(() => {
    const overview = this.overview();
    return overview && {
      recent: checkoutRate(overview.recent),
      previous: checkoutRate(overview.previous),
    };
  });

  protected readonly lastGameName = computed(() => {
    const game = this.overview()?.lastGame;
    return game ? gameTitle(game.settings) : '';
  });

  protected readonly lastGamePlayers = computed(() => {
    const game = this.overview()?.lastGame;
    return (game?.players ?? [])
      .map((player) => (player.isMe ? $localize`:@@player.list.self:Du` : player.name))
      .join(', ');
  });

  protected readonly chartData = computed<ChartData<'line'>>(() => {
    const trend = this.overview()?.recent.trend ?? [];
    return {
      labels: trend.map((point) => point.playedAt),
      datasets: [
        {
          data: trend.map((point) => point.average),
          borderColor: OWN_COLOR,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
        },
      ],
    };
  });

  protected readonly chartOptions: ChartOptions<'line'> = {
    ...chartBase(this.theme),
    events: [],
    scales: { x: { display: false }, y: { display: false } },
    plugins: { legend: { display: false }, tooltip: { enabled: false } },
  };

  constructor() {
    void this.auth.ready.then(() => this.restoring.set(false));
    effect(() => {
      if (!this.restoring() && this.user()) {
        untracked(() => void this.load());
      }
    });
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.failed.set(false);
    const since = periodStart('days30', new Date());
    const before = since && new Date(since.getFullYear(), since.getMonth(), since.getDate() - DAYS);
    try {
      const [recent, previous, games] = await Promise.all([
        this.statistics.load(x01Filter(since, null)),
        this.statistics.load(x01Filter(before, since)),
        this.history.list(1, 0),
      ]);
      this.overview.set({ recent, previous, lastGame: games.items[0] ?? null });
    } catch {
      this.failed.set(true);
    } finally {
      this.loading.set(false);
    }
  }
}
