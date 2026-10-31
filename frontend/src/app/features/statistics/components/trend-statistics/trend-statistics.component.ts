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
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { LoadErrorComponent } from '../../../../core/view/components/load-error/load-error.component';
import { LoadingStateComponent } from '../../../../core/view/components/loading-state/loading-state.component';

/** One figure game by game under the page's filters, with a running line through it. */
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

  protected readonly metricOptions = [...TREND_METRICS];
  protected readonly metric = signal<TrendMetric>('average');
  protected readonly window = TREND_WINDOW;

  protected readonly points = signal<TrendPointDto[] | null>(null);
  protected readonly failed = signal(false);
  private requests = 0;

  private readonly picked = computed(
    () => TREND_METRICS.find((option) => option.value === this.metric()) ?? TREND_METRICS[0],
  );

  protected readonly data = computed<ChartData<'line', (number | null)[]>>(() => {
    const points = this.points() ?? [];
    const metric = this.metric();
    const color = SERIES_COLORS[0];
    return {
      labels: points.map((point) => formatDate(point.playedAt, 'dd.MM.yy', this.locale)),
      datasets: [
        {
          label: 'Spiel',
          data: points.map((point) => trendValue(point, metric)),
          showLine: false,
          pointRadius: 2.5,
          pointHoverRadius: 4,
          pointBackgroundColor: `${this.theme.muted}99`,
          pointBorderWidth: 0,
        },
        {
          label: `Ø ${TREND_WINDOW} Spiele`,
          data: runningTrend(points, metric),
          borderColor: color,
          backgroundColor: color,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.3,
          spanGaps: true,
        },
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
    return latest === null
      ? label
      : `${label}, zuletzt ${latest.toFixed(1)}${this.picked().unit} im Schnitt der letzten ${TREND_WINDOW}`;
  });

  constructor() {
    effect(() => {
      const filter = this.filter();
      untracked(() => void this.load(filter));
    });
  }

  protected reload(): void {
    void this.load(this.filter());
  }

  /** Only the latest request may land, so a quick change of filters cannot be overtaken. */
  private async load(filter: StatisticsFilter): Promise<void> {
    const request = ++this.requests;
    this.points.set(null);
    this.failed.set(false);
    try {
      const points = await this.statistics.trend(filter);
      if (request === this.requests) {
        this.points.set(points);
      }
    } catch {
      if (request === this.requests) {
        this.failed.set(true);
      }
    }
  }
}
