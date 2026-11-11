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
import type { ChartData, ChartOptions } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { GameAccuracyDto } from '../../dto/accuracy.dto';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, axisTitle, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';
import { SHORT_DATE } from '../../../../core/i18n/models/date-format';
import { InfoHintComponent } from '../../../../core/view/components/info-hint/info-hint.component';

/** How many games, up to the current one, the trend line pools. */
export const TREND_WINDOW = 5;

/** Each game's share of correct darts over it and the games before it, weighted by darts. */
export function rollingAccuracy(games: readonly GameAccuracyDto[], window = TREND_WINDOW): number[] {
  return games.map((_, index) => {
    const pooled = games.slice(Math.max(0, index - window + 1), index + 1);
    const thrown = pooled.reduce((sum, game) => sum + game.summary.dartsThrown, 0);
    const correct = pooled.reduce((sum, game) => sum + game.summary.correct, 0);
    return thrown === 0 ? 0 : (100 * correct) / thrown;
  });
}

/** The parts of the chart its legend switches on and off. */
type TrendPart = 'games' | 'trend';

/** Each game's accuracy in the order they were played as dots, a rolling trend through them. */
@Component({
  selector: 'app-accuracy-trend',
  imports: [InfoHintComponent, UIChart],
  templateUrl: './accuracy-trend.component.html',
  styleUrl: './accuracy-trend.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccuracyTrendComponent {
  private readonly locale = inject(LOCALE_ID);
  private readonly theme = chartTheme(inject(DOCUMENT));

  protected readonly window = TREND_WINDOW;
  protected readonly hidden = signal<ReadonlySet<TrendPart>>(new Set());

  /** The games newest first, as the report lists them. */
  readonly games = input.required<readonly GameAccuracyDto[]>();

  /** Oldest first, and only games with a thrown dart. */
  private readonly played = computed(() =>
    [...this.games()].reverse().filter((game) => game.summary.dartsThrown > 0),
  );

  protected readonly data = computed<ChartData<'line', number[]>>(() => ({
    labels: this.played().map((game) => formatDate(game.createdAt, SHORT_DATE, this.locale)),
    datasets: [
      {
        label: $localize`:@@common.nav.game:Spiel`,
        data: this.played().map((game) => (100 * game.summary.correct) / game.summary.dartsThrown),
        hidden: this.hidden().has('games'),
        showLine: false,
        pointRadius: 3,
        pointHoverRadius: 4,
        pointBackgroundColor: `${this.theme.muted}99`,
        pointBorderWidth: 0,
        pointHitRadius: 10,
      },
      {
        label: $localize`:@@stats.tab.trend:Trend`,
        data: rollingAccuracy(this.played()),
        borderColor: SERIES_COLORS[0],
        backgroundColor: SERIES_COLORS[0],
        hidden: this.hidden().has('trend'),
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
      },
    ],
  }));

  protected readonly options = computed<ChartOptions<'line'>>(() => {
    const games = this.played();
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
          ticks: { ...axisTicks(this.theme), maxTicksLimit: 5, maxRotation: 0 },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: this.theme.border },
          border: { display: false },
          ticks: { ...axisTicks(this.theme), maxTicksLimit: 5, callback: (value) => `${value} %` },
          title: axisTitle(this.theme, $localize`:@@eval.correctSegments:Korrekte Segmente`),
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipStyle(this.theme),
          displayColors: false,
          callbacks: {
            title: (items) => {
              const game = games[items[0].dataIndex];
              const versions = game.trackerVersions.join(', ') || '–';
              return `${items[0].label} · ${game.mode ?? '–'} · Tracker ${versions}`;
            },
            label: (item) => {
              const rate = formatNumber(item.raw as number, this.locale, '1.0-0');
              if (item.datasetIndex === 1) {
                return `${item.dataset.label}: ${rate} %`;
              }
              const { correct, dartsThrown } = games[item.dataIndex].summary;
              return $localize`:@@eval.trend.tooltip:${correct}:correct: von ${dartsThrown}:thrown: Darts korrekt (${rate}:rate: %)`;
            },
          },
        },
      },
    };
  });

  protected toggle(part: TrendPart): void {
    this.hidden.update((hidden) => {
      const next = new Set(hidden);
      if (!next.delete(part)) {
        next.add(part);
      }
      return next;
    });
  }

  protected readonly ariaLabel = computed(() => {
    const played = this.played();
    const last = played.at(-1);
    const rate = last
      ? formatNumber(rollingAccuracy(played).at(-1) ?? 0, this.locale, '1.0-0')
      : '–';
    return $localize`:@@eval.trend.label:Trefferquote über ${played.length}:count: Spiele, Trend zuletzt ${rate}:rate: %`;
  });
}
