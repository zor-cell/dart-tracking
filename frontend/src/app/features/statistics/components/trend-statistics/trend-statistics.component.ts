import { DOCUMENT, formatDate } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { ChartData, ChartOptions } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { SelectButton } from 'primeng/selectbutton';
import { TrendPointDto } from '../../dto/trend-point.dto';
import { COMPARE_COLOR, OWN_COLOR } from '../../models/comparison';
import { StatisticsFilter } from '../../models/statistics-filter';
import {
  TREND_METRICS,
  TREND_WINDOW,
  TrendMetric,
  runningTrend,
  trendValue,
} from '../../models/trend-metric';
import { StatisticsService } from '../../services/statistics.service';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** One figure game by game under the page's filters, with a running line through it, and
 * a second line for a compared player. */
@Component({
  selector: 'app-trend-statistics',
  imports: [
    EmptyStateComponent,
    FormsModule,
    LoadErrorComponent,
    LoadingStateComponent,
    SelectButton,
    UIChart,
  ],
  templateUrl: './trend-statistics.component.html',
  styleUrl: './trend-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrendStatisticsComponent {
  private readonly statistics = inject(StatisticsService);
  private readonly locale = inject(LOCALE_ID);
  private readonly theme = chartTheme(inject(DOCUMENT));

  readonly filter = input.required<StatisticsFilter>();
  /** The address book entry whose line is drawn beside one's own. */
  readonly compareId = input<string | null>(null);
  readonly compareName = input<string | null>(null);

  protected readonly metricOptions = [...TREND_METRICS];
  protected readonly metric = signal<TrendMetric>('average');
  protected readonly window = TREND_WINDOW;

  protected readonly points = signal<TrendPointDto[] | null>(null);
  protected readonly otherPoints = signal<TrendPointDto[] | null>(null);
  private readonly ownColor = OWN_COLOR;
  private readonly compareColor = COMPARE_COLOR;
  protected readonly failed = signal(false);
  private requests = 0;

  private readonly picked = computed(
    () => TREND_METRICS.find((option) => option.value === this.metric()) ?? TREND_METRICS[0],
  );

  /** Both players' games on one axis, oldest first; a game they played together is one slot. */
  protected readonly data = computed<ChartData<'line', (number | null)[]>>(() => {
    const own = this.points() ?? [];
    const other = this.otherPoints();
    const metric = this.metric();
    const slots = new Map<string, string>();
    for (const point of [...own, ...(other ?? [])].sort((a, b) =>
      a.playedAt.localeCompare(b.playedAt),
    )) {
      slots.set(point.gameId, point.playedAt);
    }
    const ids = [...slots.keys()];
    const series = (points: readonly TrendPointDto[], name: string | null, color: string) => {
      const value = new Map(points.map((point) => [point.gameId, trendValue(point, metric)]));
      const running = runningTrend(points, metric);
      const trend = new Map(points.map((point, index) => [point.gameId, running[index]]));
      const prefix = name ? `${name} · ` : '';
      return [
        {
          label: `${prefix}Spiel`,
          data: ids.map((id) => value.get(id) ?? null),
          showLine: false,
          pointRadius: 2.5,
          pointHoverRadius: 4,
          pointBackgroundColor: name ? `${color}66` : `${this.theme.muted}99`,
          pointBorderWidth: 0,
        },
        {
          label: `${prefix}Ø ${TREND_WINDOW} Spiele`,
          data: ids.map((id) => trend.get(id) ?? null),
          borderColor: color,
          backgroundColor: color,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.3,
          spanGaps: true,
        },
      ];
    };
    const compared = other ? (this.compareName() ?? '') : null;
    return {
      labels: [...slots.values()].map((at) => formatDate(at, 'dd.MM.yy', this.locale)),
      datasets: [
        ...series(own, compared === null ? null : 'Du', this.ownColor),
        ...(other && compared !== null ? series(other, compared, this.compareColor) : []),
      ],
    };
  });

  protected readonly options = computed<ChartOptions<'line'>>(() => {
    const unit = this.picked().unit;
    const format = (value: number) => `${value.toFixed(1).replace('.', ',')}${unit}`;
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      font: { family: this.theme.font },
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { ...axisTicks(this.theme), maxTicksLimit: 4, maxRotation: 0 },
        },
        y: {
          grid: { color: this.theme.grid },
          border: { display: false },
          ticks: { ...axisTicks(this.theme), maxTicksLimit: 5 },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipStyle(this.theme),
          callbacks: {
            label: (item) => `${item.dataset.label}: ${format(item.raw as number)}`,
          },
          filter: (item) => item.raw !== null,
        },
      },
    };
  });

  /** The figure and where its running line ends, for screen readers. */
  protected readonly ariaLabel = computed(() => {
    const points = this.points() ?? [];
    const latest = runningTrend(points, this.metric()).at(-1) ?? null;
    const label = `${this.picked().label} über ${points.length} Spiele`;
    const own =
      latest === null
        ? label
        : `${label}, zuletzt ${latest.toFixed(1)}${this.picked().unit} im Schnitt der letzten ${TREND_WINDOW}`;
    const other = this.otherPoints();
    const theirs = other ? (runningTrend(other, this.metric()).at(-1) ?? null) : null;
    return theirs === null
      ? own
      : `${own}; ${this.compareName()} zuletzt ${theirs.toFixed(1)}${this.picked().unit}`;
  });

  constructor() {
    effect(() => {
      const filter = this.filter();
      const compared = this.compareId();
      untracked(() => void this.load(filter, compared));
    });
  }

  protected reload(): void {
    void this.load(this.filter(), this.compareId());
  }

  /** Only the latest request may land, so a quick change of filters cannot be overtaken. */
  private async load(filter: StatisticsFilter, compared: string | null): Promise<void> {
    const request = ++this.requests;
    this.points.set(null);
    this.failed.set(false);
    try {
      const [points, others] = await Promise.all([
        this.statistics.trend(filter),
        compared ? this.statistics.trend(filter, compared) : null,
      ]);
      if (request === this.requests) {
        this.points.set(points);
        this.otherPoints.set(others);
      }
    } catch {
      if (request === this.requests) {
        this.failed.set(true);
      }
    }
  }
}
