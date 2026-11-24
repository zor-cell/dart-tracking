import { DOCUMENT, formatDate, formatNumber } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { ChartData, ChartOptions } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { SelectButton } from 'primeng/selectbutton';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, chartBase, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';
import {
  DAY_MONTH,
  LONG_MONTH_YEAR,
  MONTH_YEAR,
  WEEKDAY_DAY_MONTH,
} from '../../../../core/i18n/models/date-format';
import { GAME_SECTIONS } from '../../../game/models/game-variant';
import { ActivityBucketDto, ActivityDto, ActivityTallyDto, ActivityUnit } from '../../dto/activity.dto';
import { toggled } from '../../models/linear-fit';
import { duration } from '../../models/duration';
import { TrendLegendComponent, TrendLegendEntry } from '../trend-legend/trend-legend.component';

type ActivityMetric = 'darts' | 'games' | 'time';

const METRICS: readonly { label: string; value: ActivityMetric }[] = [
  { label: $localize`:@@stats.all.metric.darts:Darts`, value: 'darts' },
  { label: $localize`:@@stats.all.metric.games:Spiele`, value: 'games' },
  { label: $localize`:@@stats.all.metric.time:Zeit`, value: 'time' },
];

const PER_UNIT: Record<ActivityUnit, string> = {
  day: $localize`:@@stats.all.perDay:pro Tag`,
  week: $localize`:@@stats.all.perWeek:pro Woche`,
  month: $localize`:@@stats.all.perMonth:pro Monat`,
};

/** One kind of game as the chart stacks it, with its value per bucket. */
interface KindSeries {
  readonly key: string;
  readonly label: string;
  readonly color: string;
  readonly values: readonly number[];
  readonly total: number;
}

/** How much was played when: darts, games or time per bucket, stacked by kind of game. */
@Component({
  selector: 'app-activity-chart',
  imports: [FormsModule, SelectButton, TrendLegendComponent, UIChart],
  templateUrl: './activity-chart.component.html',
  styleUrl: './activity-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActivityChartComponent {
  private readonly locale = inject(LOCALE_ID);
  private readonly theme = chartTheme(inject(DOCUMENT));

  readonly activity = input.required<ActivityDto>();

  protected readonly metrics = [...METRICS];
  protected readonly metric = signal<ActivityMetric>('darts');
  protected readonly hidden = signal<ReadonlySet<string>>(new Set());

  protected readonly perUnit = computed(() => PER_UNIT[this.activity().unit]);

  /** The kinds played in the span, in the order of the new game page. */
  private readonly series = computed<KindSeries[]>(() => {
    const metric = this.metric();
    const buckets = this.activity().buckets;
    return GAME_SECTIONS.map((section, index) => {
      const values = buckets.map((bucket) =>
        section.games.reduce((sum, game) => sum + measure(bucket.variants[game], metric), 0),
      );
      return {
        key: section.kind,
        label: section.kind,
        color: SERIES_COLORS[index],
        values,
        total: values.reduce((sum, value) => sum + value, 0),
      };
    }).filter((series) => series.total > 0);
  });

  protected readonly legend = computed<TrendLegendEntry[]>(() =>
    this.series().map((series) => ({
      key: series.key,
      label: `${series.label} (${this.figure(series.total)})`,
      swatch: 'box',
      color: series.color,
    })),
  );

  protected readonly ariaLabel = computed(
    () => `${METRICS.find((metric) => metric.value === this.metric())?.label} ${this.perUnit()}`,
  );

  protected readonly data = computed<ChartData<'bar'>>(() => {
    const hidden = this.hidden();
    return {
      labels: this.activity().buckets.map((bucket) => this.tick(bucket)),
      datasets: this.series().map((series) => ({
        label: series.label,
        data: [...series.values],
        backgroundColor: series.color,
        borderRadius: 1,
        hidden: hidden.has(series.key),
      })),
    };
  });

  protected readonly options = computed<ChartOptions<'bar'>>(() => {
    const theme = this.theme;
    const buckets = this.activity().buckets;
    const time = this.metric() === 'time';
    return {
      ...chartBase(theme),
      datasets: { bar: { categoryPercentage: 0.85, barPercentage: 0.9 } },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipStyle(theme),
          boxWidth: 8,
          boxHeight: 8,
          filter: (item) => (item.parsed.y ?? 0) > 0,
          callbacks: {
            title: (items) => (items.length === 0 ? [] : this.title(buckets[items[0].dataIndex])),
            label: (item) => ` ${item.dataset.label}: ${this.figure(item.parsed.y ?? 0)}`,
            footer: (items) => {
              if (items.length === 0) {
                return [];
              }
              const total = items.reduce((sum, item) => sum + (item.parsed.y ?? 0), 0);
              return $localize`:@@stats.all.together:Zusammen ${this.figure(total)}:total:`;
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          ticks: { ...axisTicks(theme), maxTicksLimit: 6, maxRotation: 0 },
          grid: { display: false },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          ticks: {
            ...axisTicks(theme),
            precision: 0,
            maxTicksLimit: 5,
            callback: (value) => (time ? `${value} h` : formatNumber(+value, this.locale, '1.0-0')),
          },
          grid: { color: theme.border },
          border: { display: false },
        },
      },
    };
  });

  protected toggle(key: string): void {
    this.hidden.update((hidden) => toggled(hidden, key));
  }

  /** A value of the chart as it reads; time is charted in hours. */
  private figure(value: number): string {
    return this.metric() === 'time'
      ? duration(value * 3600, this.locale)
      : formatNumber(value, this.locale, '1.0-0');
  }

  private tick({ start }: ActivityBucketDto): string {
    return formatDate(start, this.activity().unit === 'month' ? MONTH_YEAR : DAY_MONTH, this.locale);
  }

  private title({ start }: ActivityBucketDto): string {
    switch (this.activity().unit) {
      case 'day':
        return formatDate(start, WEEKDAY_DAY_MONTH, this.locale);
      case 'week':
        return $localize`:@@stats.all.weekOf:Woche ab ${formatDate(start, DAY_MONTH, this.locale)}:date:`;
      case 'month':
        return formatDate(start, LONG_MONTH_YEAR, this.locale);
    }
  }
}

/** What a tally adds to the chart in `metric`; time in hours. */
function measure(tally: ActivityTallyDto | undefined, metric: ActivityMetric): number {
  if (!tally) {
    return 0;
  }
  return metric === 'darts' ? tally.darts : metric === 'games' ? tally.games : tally.seconds / 3600;
}
