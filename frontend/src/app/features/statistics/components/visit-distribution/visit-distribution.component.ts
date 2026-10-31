import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import type { ChartData, ChartOptions } from 'chart.js';
import { FormsModule } from '@angular/forms';
import { UIChart } from 'primeng/chart';
import { SelectButton } from 'primeng/selectbutton';
import {
  VISIT_BIN_WIDTHS,
  VisitBin,
  VisitBinWidth,
  topVisits,
  visitBins,
} from '../../models/visit-bins';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';

/** How many of the most frequent visits are named under the bars. */
const TOP_VISITS = 5;

/** Every unbusted visit as bars of ten points or one per score, the most frequent scores named
 * below; a tapped bar names the scores in it instead. */
@Component({
  selector: 'app-visit-distribution',
  imports: [FormsModule, SelectButton, UIChart],
  templateUrl: './visit-distribution.component.html',
  styleUrl: './visit-distribution.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VisitDistributionComponent {
  private readonly theme = chartTheme(inject(DOCUMENT));

  /** Visits by their points, keyed as the statistics send them. */
  readonly visitScores = input.required<Readonly<Record<string, number>>>();

  protected readonly widthOptions = [...VISIT_BIN_WIDTHS];
  protected readonly width = signal<VisitBinWidth>(10);
  protected readonly bins = computed(() => visitBins(this.visitScores(), this.width()));
  protected readonly picked = signal<VisitBin | null>(null);
  protected readonly top = computed(() => topVisits(this.visitScores(), TOP_VISITS));
  protected readonly total = computed(() => this.bins().reduce((sum, bin) => sum + bin.total, 0));

  protected readonly data = computed<ChartData<'bar', number[]>>(() => {
    const picked = this.picked();
    const color = SERIES_COLORS[0];
    return {
      labels: this.bins().map((bin) => `${bin.from}`),
      datasets: [
        {
          label: 'Visits',
          data: this.bins().map((bin) => bin.total),
          backgroundColor: this.bins().map((bin) =>
            picked === null || picked.from === bin.from ? color : `${color}55`,
          ),
          borderRadius: this.width() === 1 ? 0 : 2,
          categoryPercentage: this.width() === 1 ? 1 : 0.9,
          barPercentage: 0.9,
        },
      ],
    };
  });

  protected readonly options = computed<ChartOptions<'bar'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    font: { family: this.theme.font },
    onClick: (_, elements) => this.pick(elements[0]?.index ?? null),
    scales: {
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: {
          ...axisTicks(this.theme),
          maxRotation: 0,
          // Single scores keep round marks only; 181 labels would fall at random.
          autoSkip: this.width() !== 1,
          autoSkipPadding: 6,
          callback: (_, index) =>
            this.width() === 1 && index % 20 !== 0 ? '' : `${this.bins()[index].from}`,
        },
      },
      y: {
        grid: { color: this.theme.grid },
        border: { display: false },
        ticks: { ...axisTicks(this.theme), maxTicksLimit: 4, precision: 0 },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        ...tooltipStyle(this.theme),
        callbacks: {
          title: (items) => this.rangeOf(this.bins()[items[0]?.dataIndex ?? 0]),
          label: (item) => `${item.raw} Visits`,
        },
      },
    },
  }));

  protected readonly ariaLabel = computed(() => {
    const named = this.top()
      .map((entry) => `${entry.score} ${entry.count}-mal`)
      .join(', ');
    const steps = this.width() === 1 ? 'einzeln' : 'in Zehnerschritten';
    return `${this.total()} Visits nach Punkten ${steps}. Am häufigsten: ${named}`;
  });

  /** "40–49", or a single score. */
  protected rangeOf(bin: VisitBin): string {
    return bin.from === bin.to ? `${bin.from}` : `${bin.from}–${bin.to}`;
  }

  /** Switches the bar width and lets go of the picked bar, which no longer exists. */
  protected selectWidth(width: VisitBinWidth): void {
    this.width.set(width);
    this.picked.set(null);
  }

  /** A tap on a bar names its scores; a second tap, or one beside the bars, goes back. */
  private pick(index: number | null): void {
    const bin = index === null ? null : this.bins()[index];
    this.picked.update((picked) => (bin === null || picked?.from === bin?.from ? null : bin));
  }
}
