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
import type { ChartData, ChartOptions, ScriptableLineSegmentContext } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { SelectButton } from 'primeng/selectbutton';
import { COMPARE_COLOR, OWN_COLOR } from '../../models/comparison';
import { FIT_COLOR, FIT_LEGEND, linearFit, toggled } from '../../models/linear-fit';
import {
  TREND_WINDOW,
  TrendFigure,
  TrendGame,
  rollingAverage,
} from '../../models/trend-metric';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, axisTitle, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { EmptyStateComponent } from '../../../../core/view/components/empty-state/empty-state.component';
import { TrendLegendComponent, TrendLegendEntry } from '../trend-legend/trend-legend.component';

/** The parts of the chart its legend switches on and off. */
type TrendPart = 'games' | 'form' | 'trend';

/** Dash and gap of a trend line where its player has no game, in pixels. */
const GAP_DASH = [4, 4];

/** Dash and gap of the compared player's fitted line, in pixels. */
const FIT_DASH = [6, 3];

/** One figure game by game under the page's filters, with the form (a rolling mean) and the
 * trend (a fitted straight line) through it, and the same for a compared player. */
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

  /** Both players' games on one axis, oldest first; a game they played together is one slot. */
  protected readonly data = computed<ChartData<'line', (number | null)[]>>(() => {
    const own = this.points();
    const other = this.otherPoints();
    const figure = this.picked();
    const hidden = this.hidden();
    const slots = new Map<string, string>();
    for (const point of [...own, ...(other ?? [])].sort((a, b) =>
      a.playedAt.localeCompare(b.playedAt),
    )) {
      slots.set(point.gameId, point.playedAt);
    }
    const ids = [...slots.keys()];
    const series = (points: readonly T[], name: string | null, color: string) => {
      const value = new Map(points.map((point) => [point.gameId, figure.of(point)]));
      const values = ids.map((id) => value.get(id) ?? null);
      const rolling = rollingAverage(points.map(figure.of));
      const form = new Map(points.map((point, index) => [point.gameId, rolling[index]]));
      return [
        {
          label: withName($localize`:@@common.nav.game:Spiel`, name),
          data: values,
          hidden: hidden.has('games'),
          showLine: false,
          pointRadius: 2.5,
          pointHoverRadius: 4,
          pointBackgroundColor: name ? `${color}66` : `${this.theme.muted}99`,
          pointBorderWidth: 0,
        },
        {
          label: withName($localize`:@@stats.trend.form:Form`, name),
          data: ids.map((id) => form.get(id) ?? null),
          borderColor: color,
          backgroundColor: color,
          hidden: hidden.has('form'),
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.3,
          spanGaps: true,
          // Dashed across games the player did not play in.
          segment: {
            borderDash: (segment: ScriptableLineSegmentContext) =>
              segment.p0.skip || segment.p1.skip ? GAP_DASH : undefined,
          },
        },
        {
          label: withName(FIT_LEGEND.label, name),
          data: linearFit(values),
          borderColor: FIT_COLOR,
          backgroundColor: FIT_COLOR,
          hidden: hidden.has('trend'),
          borderWidth: 1.5,
          // The compared player's line dashed, so the two stay apart.
          borderDash: color === this.compareColor ? FIT_DASH : undefined,
          pointRadius: 0,
          pointHoverRadius: 0,
          spanGaps: true,
        },
      ];
    };
    const compared = other ? (this.compareName() ?? '') : null;
    return {
      labels: [...slots.values()].map((at) => formatDate(at, SHORT_DATE, this.locale)),
      datasets: [
        ...series(own, compared === null ? null : $localize`:@@player.list.self:Du`, this.ownColor),
        ...(other && compared !== null ? series(other, compared, this.compareColor) : []),
      ],
    };
  });

  protected readonly options = computed<ChartOptions<'line'>>(() => {
    const { unit, axis } = this.picked();
    const format = (value: number) => `${formatNumber(value, this.locale, '1.1-1')}${unit}`;
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
          title: axisTitle(this.theme, axis),
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

  /** The legend's switches; the trend line takes one's own colour unless players are compared. */
  protected readonly legend = computed<TrendLegendEntry[]>(() => [
    { key: 'games', label: $localize`:@@stats.trend.games:Einzelne Spiele`, swatch: 'dot' },
    {
      key: 'form',
      label: $localize`:@@stats.trend.form:Form`,
      swatch: 'line',
      color: this.otherPoints() ? undefined : this.ownColor,
      hint: $localize`:@@stats.trend.hint:Schnitt über die letzten ${TREND_WINDOW}:INTERPOLATION: Spiele.`,
    },
    FIT_LEGEND,
  ]);

  protected toggle(part: string): void {
    this.hidden.update((hidden) => toggled(hidden, part as TrendPart));
  }

  /** The figure and where its trend line ends, for screen readers. */
  protected readonly ariaLabel = computed(() => {
    const points = this.points();
    const figure = this.picked();
    const latest = rollingAverage(points.map(figure.of)).at(-1) ?? null;
    const label = $localize`:@@stats.trend.label:${this.picked().label}:metric: über ${points.length}:count: Spiele`;
    const own =
      latest === null
        ? label
        : $localize`:@@stats.trend.latest:${label}:label:, Trend zuletzt ${latest.toFixed(1)}:value:${this.picked().unit}:unit:`;
    const other = this.otherPoints();
    const theirs = other ? (rollingAverage(other.map(figure.of)).at(-1) ?? null) : null;
    return theirs === null
      ? own
      : $localize`:@@stats.trend.theirs:${own}:own:; ${this.compareName()}:name: zuletzt ${theirs.toFixed(1)}:value:${this.picked().unit}:unit:`;
  });
}

/** A series label, with the player's name in brackets when players are compared. */
function withName(label: string, name: string | null): string {
  return name ? `${label} (${name})` : label;
}
