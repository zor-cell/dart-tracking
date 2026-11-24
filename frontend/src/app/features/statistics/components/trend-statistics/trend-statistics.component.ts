import { DOCUMENT, formatDate, formatNumber } from '@angular/common';
import { SHORT_DATE } from '../../../../core/i18n/models/date-format';
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
import type { ChartData, ChartOptions, Point } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { SelectButton } from 'primeng/selectbutton';
import { COMPARE_COLOR, OWN_COLOR } from '../../models/comparison';
import { FIT_COLOR, FIT_LEGEND, linearFit, linearFitOver, toggled } from '../../models/linear-fit';
import {
  TREND_WINDOW,
  TrendFigure,
  TrendGame,
  rollingAverage,
} from '../../models/trend-metric';
import { DOT_ROOM, axisBounds } from '../../../../core/charts/models/axis-bounds';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, axisTitle, chartBase, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { TrendLegendComponent, TrendLegendEntry } from '../trend-legend/trend-legend.component';

/** The parts of the chart its legend switches on and off. */
type TrendPart = 'games' | 'form' | 'trend';

/** Dash and gap of the fitted lines beside a compared player, in pixels. */
const FIT_DASH = [5, 4];

/** One figure game by game under the page's filters, with the form (a rolling mean) and the
 * trend (a fitted straight line) through it. Beside a compared player both run over the dates,
 * each in its player's colour, the trend dashed. */
@Component({
  selector: 'app-trend-statistics',
  imports: [EmptyStateComponent, FormsModule, SelectButton, TrendLegendComponent, UIChart],
  templateUrl: './trend-statistics.component.html',
  styleUrl: './trend-statistics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrendStatisticsComponent<T extends TrendGame> {
  private readonly locale = inject(LOCALE_ID);
  private readonly theme = chartTheme(inject(DOCUMENT));

  /** The page's games one by one, oldest first, as the statistics bring them. */
  readonly points = input.required<readonly T[]>();
  /** The compared player's games, drawn as a second line beside one's own. */
  readonly otherPoints = input<readonly T[] | null>(null);
  readonly compareName = input<string | null>(null);
  /** The figures the chart can follow, the first shown at the start. */
  readonly figures = input.required<readonly TrendFigure<T>[]>();

  protected readonly metricOptions = computed(() => [...this.figures()]);
  protected readonly metric = signal<string | null>(null);
  protected readonly hidden = signal<ReadonlySet<TrendPart>>(new Set());

  private readonly ownColor = OWN_COLOR;
  private readonly compareColor = COMPARE_COLOR;

  protected readonly picked = computed(
    () => this.figures().find((figure) => figure.value === this.metric()) ?? this.figures()[0],
  );

  /** The games the picked figure is drawn over: all of them, or those that have it. */
  protected readonly shown = computed(() => this.withFigure(this.points()));
  private readonly otherShown = computed(() => {
    const other = this.otherPoints();
    return other && this.withFigure(other);
  });

  private withFigure(points: readonly T[]): readonly T[] {
    const figure = this.picked();
    return figure.sparse ? points.filter((point) => figure.of(point) !== null) : points;
  }

  /** Whether a compared player's games are drawn beside one's own. */
  private readonly compared = computed(() => this.otherShown() !== null && this.compareName() !== null);

  protected readonly data = computed<ChartData<'line', (number | Point | null)[]>>(() =>
    this.compared() ? this.byDate() : this.byGame(),
  );

  /** One's own games side by side, one slot each. */
  private byGame(): ChartData<'line', (number | null)[]> {
    const figure = this.picked();
    const points = this.shown();
    const hidden = this.hidden();
    const values = points.map(figure.of);
    return {
      labels: points.map((point) => formatDate(point.playedAt, SHORT_DATE, this.locale)),
      datasets: [
        { ...this.dots(`${this.theme.muted}99`), label: GAME_LABEL, data: values, hidden: hidden.has('games') },
        {
          ...this.formLine(this.ownColor),
          label: FORM_LABEL,
          data: rollingAverage(values),
          hidden: hidden.has('form'),
        },
        {
          label: FIT_LEGEND.label,
          data: linearFit(values),
          borderColor: FIT_COLOR,
          backgroundColor: FIT_COLOR,
          hidden: hidden.has('trend'),
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 0,
          spanGaps: true,
        },
      ],
    };
  }

  /** Both players over the dates, each line only through its own games. */
  private byDate(): ChartData<'line', (Point | null)[]> {
    const figure = this.picked();
    const hidden = this.hidden();
    const side = (points: readonly T[], name: string, color: string) => {
      const xs = points.map((point) => Date.parse(point.playedAt));
      const values = points.map(figure.of);
      const at = (ys: readonly (number | null)[]) =>
        xs.flatMap((x, index) => (ys[index] === null ? [] : [{ x, y: ys[index] as number }]));
      return [
        {
          ...this.dots(`${color}66`),
          label: withName(GAME_LABEL, name),
          data: at(values),
          hidden: hidden.has('games'),
        },
        {
          ...this.formLine(color),
          // Games close together in time would make a smoothed curve overshoot.
          cubicInterpolationMode: 'monotone' as const,
          label: withName(FORM_LABEL, name),
          data: at(rollingAverage(values)),
          hidden: hidden.has('form'),
        },
        {
          label: withName(FIT_LEGEND.label, name),
          data: linearFitOver(xs, values),
          borderColor: color,
          backgroundColor: color,
          hidden: hidden.has('trend'),
          borderWidth: 1.5,
          borderDash: FIT_DASH,
          pointRadius: 0,
          pointHoverRadius: 0,
        },
      ];
    };
    return {
      datasets: [
        ...side(this.shown(), $localize`:@@player.list.self:Du`, this.ownColor),
        ...side(this.otherShown() ?? [], this.compareName() ?? '', this.compareColor),
      ],
    };
  }

  private dots(color: string) {
    return {
      showLine: false,
      clip: DOT_ROOM,
      pointRadius: 2.5,
      pointHoverRadius: 4,
      pointBackgroundColor: color,
      pointBorderWidth: 0,
    };
  }

  private formLine(color: string) {
    return {
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.3,
      spanGaps: true,
    };
  }

  /** The value axis around the games and form lines of both players; the fitted line is clipped. */
  private readonly bounds = computed(() => {
    const figure = this.picked();
    const values = [this.shown(), this.otherShown() ?? []].flatMap((points) => {
      const figures = points.map(figure.of);
      return [...figures, ...rollingAverage(figures)];
    });
    return axisBounds(values, figure.unit.trim() === '%');
  });

  protected readonly options = computed<ChartOptions<'line'>>(() => {
    const { unit, axis } = this.picked();
    const format = (value: number) => `${formatNumber(value, this.locale, '1.1-1')}${unit}`;
    const bounds = this.bounds();
    const dated = this.compared();
    const span = dated ? this.span() : null;
    return {
      ...chartBase(this.theme),
      layout: { padding: { top: DOT_ROOM, right: DOT_ROOM } },
      interaction: dated ? { mode: 'nearest', axis: 'x', intersect: false } : { mode: 'index', intersect: false },
      scales: {
        x: {
          ...(dated
            ? {
                type: 'linear' as const,
                min: span?.min,
                max: span?.max,
                // Four dates spread evenly, the first and last day at the ends.
                afterBuildTicks: (axis: { ticks: { value: number }[] }) => {
                  axis.ticks = span ? evenly(span.min, span.max, 4).map((value) => ({ value })) : [];
                },
              }
            : {}),
          grid: { display: false },
          border: { display: false },
          ticks: {
            ...axisTicks(this.theme),
            maxTicksLimit: 4,
            maxRotation: 0,
            ...(dated ? { callback: (value: string | number) => this.date(+value) } : {}),
          },
        },
        y: {
          min: bounds?.min,
          max: bounds?.max,
          grid: { color: this.theme.grid },
          border: { display: false },
          ticks: { ...axisTicks(this.theme), maxTicksLimit: 5 },
          title: axisTitle(this.theme, axis),
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipStyle(this.theme),
          callbacks: {
            ...(dated ? { title: (items) => (items[0] ? this.date(items[0].parsed.x ?? 0) : '') } : {}),
            label: (item) => `${item.dataset.label}: ${format(item.parsed.y ?? 0)}`,
          },
          filter: (item) => item.raw !== null,
        },
      },
    };
  });

  /** The legend's switches; beside a compared player the colours stand for the players, so
   * the lines show only their stroke. */
  protected readonly legend = computed<TrendLegendEntry[]>(() => {
    const compared = this.compared();
    return [
      { key: 'games', label: $localize`:@@stats.trend.games:Einzelne Spiele`, swatch: 'dot' },
      {
        key: 'form',
        label: FORM_LABEL,
        swatch: 'line',
        color: compared ? undefined : this.ownColor,
        hint: $localize`:@@stats.trend.hint:Schnitt über die letzten ${TREND_WINDOW}:INTERPOLATION: Spiele.`,
      },
      compared ? { ...FIT_LEGEND, swatch: 'dash', color: undefined } : FIT_LEGEND,
    ];
  });

  /** The first and last day either player played, as the date axis's ends. */
  private readonly span = computed(() => {
    const times = [...this.shown(), ...(this.otherShown() ?? [])].map((point) =>
      Date.parse(point.playedAt),
    );
    return times.length === 0 ? null : { min: Math.min(...times), max: Math.max(...times) };
  });

  private date(time: number): string {
    return formatDate(time, SHORT_DATE, this.locale);
  }

  protected toggle(part: string): void {
    this.hidden.update((hidden) => toggled(hidden, part as TrendPart));
  }

  /** The figure and where its trend line ends, for screen readers. */
  protected readonly ariaLabel = computed(() => {
    const points = this.shown();
    const figure = this.picked();
    const latest = rollingAverage(points.map(figure.of)).at(-1) ?? null;
    const label = $localize`:@@stats.trend.label:${this.picked().label}:metric: über ${points.length}:count: Spiele`;
    const own =
      latest === null
        ? label
        : $localize`:@@stats.trend.latest:${label}:label:, Trend zuletzt ${latest.toFixed(1)}:value:${this.picked().unit}:unit:`;
    const other = this.otherShown();
    const theirs = other ? (rollingAverage(other.map(figure.of)).at(-1) ?? null) : null;
    return theirs === null
      ? own
      : $localize`:@@stats.trend.theirs:${own}:own:; ${this.compareName()}:name: zuletzt ${theirs.toFixed(1)}:value:${this.picked().unit}:unit:`;
  });
}

/** `count` values from `min` to `max` at even steps, both ends included. */
function evenly(min: number, max: number, count: number): number[] {
  return Array.from({ length: count }, (_, index) => min + ((max - min) * index) / (count - 1));
}

const GAME_LABEL = $localize`:@@common.nav.game:Spiel`;
const FORM_LABEL = $localize`:@@stats.trend.form:Form`;

/** A series label with the player's name in brackets. */
function withName(label: string, name: string): string {
  return `${label} (${name})`;
}
