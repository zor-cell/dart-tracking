import { DOCUMENT } from '@angular/common';
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
import { MAX_VISIT, topVisits, visitCounts } from '../../models/visit-scores';
import { chartTheme, indexMarkerPlugin } from '../../../../core/charts/models/chart-plugins';
import { axisTicks } from '../../../../core/charts/models/chart-styles';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';

/** How many of the most frequent visits are offered under the bars. */
const TOP_VISITS = 5;

/** Every unbusted visit by its score, all 181 bars at once. A finger dragged across the bars
 * picks the score under it, the arrows step one score, and a top visit jumps to its own. */
@Component({
  selector: 'app-visit-distribution',
  imports: [Button, UIChart],
  templateUrl: './visit-distribution.component.html',
  styleUrl: './visit-distribution.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VisitDistributionComponent {
  private readonly theme = chartTheme(inject(DOCUMENT));

  /** Visits by their points, keyed as the statistics send them. */
  readonly visitScores = input.required<Readonly<Record<string, number>>>();

  protected readonly maxVisit = MAX_VISIT;
  protected readonly counts = computed(() => visitCounts(this.visitScores()));
  protected readonly top = computed(() => topVisits(this.visitScores(), TOP_VISITS));
  /** The score picked; opens on the most frequent one. */
  protected readonly selected = linkedSignal(() => this.top()[0]?.score ?? 0);

  protected readonly plugins: Plugin<'bar'>[] = [indexMarkerPlugin<'bar'>(() => this.selected())];

  private readonly chart = viewChild(UIChart);

  protected readonly data = computed<ChartData<'bar', number[]>>(() => ({
    labels: this.counts().map((_, score) => `${score}`),
    datasets: [
      {
        label: 'Visits',
        data: this.counts(),
        backgroundColor: SERIES_COLORS[0],
        categoryPercentage: 1,
        barPercentage: 0.85,
      },
    ],
  }));

  protected readonly options = computed<ChartOptions<'bar'>>(() => ({
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
        grid: { color: this.theme.grid },
        border: { display: false },
        ticks: { ...axisTicks(this.theme), maxTicksLimit: 4, precision: 0 },
      },
    },
    plugins: { legend: { display: false }, tooltip: { enabled: false } },
  }));

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
