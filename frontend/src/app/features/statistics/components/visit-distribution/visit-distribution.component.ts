import { DecimalPipe, DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  viewChild,
} from '@angular/core';
import type { ChartData, ChartOptions, Plugin } from 'chart.js';
import { Button } from 'primeng/button';
import { UIChart } from 'primeng/chart';
import { COMPARE_COLOR, Comparison, OWN_COLOR } from '../../models/comparison';
import { MAX_VISIT, topVisits, visitCounts, visitShares } from '../../models/visit-scores';
import { chartTheme, indexMarkerPlugin } from '../../../../core/charts/models/chart-plugins';
import { axisTicks } from '../../../../core/charts/models/chart-styles';
import { RepeatPressDirective } from '../../../../core/view/directives/repeat-press.directive';

/** How many of the most frequent visits are offered under the bars. */
const TOP_VISITS = 5;

/** Every unbusted visit by its score, all 181 bars at once. A finger dragged across the bars
 * picks the score under it, the arrows step one score, and a top visit jumps to its own.
 * Beside a compared player both read as shares, theirs mirrored below the axis. */
@Component({
  selector: 'app-visit-distribution',
  imports: [Button, DecimalPipe, RepeatPressDirective, UIChart],
  templateUrl: './visit-distribution.component.html',
  styleUrl: './visit-distribution.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VisitDistributionComponent {
  private readonly theme = chartTheme(inject(DOCUMENT));

  /** Visits by their points, keyed as the statistics send them. */
  readonly visitScores = input.required<Readonly<Record<string, number>>>();
  readonly comparison = input<Comparison | null>(null);

  protected readonly maxVisit = MAX_VISIT;
  protected readonly counts = computed(() => visitCounts(this.visitScores()));
  /** Each score's share of the visits in percent, one's own and the compared player's. */
  protected readonly shares = computed(() => visitShares(this.visitScores()));
  protected readonly otherShares = computed(() => {
    const other = this.comparison()?.statistics.visitScores;
    return other ? visitShares(other) : null;
  });
  protected readonly top = computed(() => topVisits(this.visitScores(), TOP_VISITS));
  /** The score picked; opens on the most frequent one. */
  protected readonly selected = linkedSignal(() => this.top()[0]?.score ?? 0);

  protected readonly plugins: Plugin<'bar'>[] = [indexMarkerPlugin<'bar'>(() => this.selected())];

  private readonly chart = viewChild(UIChart);

  protected readonly data = computed<ChartData<'bar', number[]>>(() => {
    const others = this.otherShares();
    const bar = { categoryPercentage: 1, barPercentage: 0.85 };
    return {
      labels: this.counts().map((_, score) => `${score}`),
      datasets: [
        {
          ...bar,
          label: 'Du',
          data: others ? this.shares() : this.counts(),
          backgroundColor: OWN_COLOR,
        },
        ...(others
          ? [
              {
                ...bar,
                label: this.comparison()?.name ?? '',
                data: others.map((share) => -share),
                backgroundColor: COMPARE_COLOR,
              },
            ]
          : []),
      ],
    };
  });

  /** In a comparison the shares mirror at zero, both halves on the same scale. */
  protected readonly options = computed<ChartOptions<'bar'>>(() => {
    const others = this.otherShares();
    const reach = others ? Math.ceil(Math.max(1, ...this.shares(), ...others)) : undefined;
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      font: { family: this.theme.font },
      // The column under the pointer counts, not just the bar itself.
      interaction: { mode: 'index', intersect: false },
      events: ['mousemove', 'click', 'touchstart', 'touchmove'],
      onHover: (_, elements) => this.pick(elements[0]?.index),
      onClick: (_, elements) => this.pick(elements[0]?.index),
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          border: { display: false },
          ticks: {
            ...axisTicks(this.theme),
            maxRotation: 0,
            autoSkip: false,
            callback: (value) => (Number(value) % 20 === 0 ? `${value}` : ''),
          },
        },
        y: {
          stacked: true,
          min: reach === undefined ? undefined : -reach,
          max: reach,
          grid: {
            color: (context) => (context.tick.value === 0 ? this.theme.muted : this.theme.grid),
          },
          border: { display: false },
          ticks: others
            ? {
                ...axisTicks(this.theme),
                maxTicksLimit: 5,
                callback: (value) => `${Math.abs(Number(value))} %`,
              }
            : { ...axisTicks(this.theme), maxTicksLimit: 4, precision: 0 },
        },
      },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    };
  });

  protected readonly ariaLabel = computed(() => {
    const named = this.top()
      .map((entry) => `${entry.score} ${entry.count}-mal`)
      .join(', ');
    return `Visits nach Punkten von 0 bis ${MAX_VISIT}. Am häufigsten: ${named}`;
  });

  constructor() {
    // The bars stay as they are; only the marker moves, so the chart is redrawn by hand.
    effect(() => {
      this.selected();
      this.chart()?.chart?.draw();
    });
  }

  protected step(by: -1 | 1): void {
    this.selected.update((score) => Math.min(MAX_VISIT, Math.max(0, score + by)));
  }

  private pick(index: number | undefined): void {
    if (index !== undefined) {
      this.selected.set(index);
    }
  }
}
