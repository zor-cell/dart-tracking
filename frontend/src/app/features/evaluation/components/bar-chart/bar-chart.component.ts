import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, model } from '@angular/core';
import type { ChartData, ChartOptions, Plugin, ScriptableContext } from 'chart.js';
import { UIChart } from 'primeng/chart';
import { chartTheme } from '../../../../core/charts/models/chart-plugins';
import { axisTicks, axisTitle, tooltipStyle } from '../../../../core/charts/models/chart-styles';
import { SERIES_COLORS } from '../../../../core/charts/models/series-colors';

/** One stacked part of every bar, named in the legend. */
export interface BarSeries {
  readonly label: string;
  readonly color: string;
  /** Drawn in diagonal stripes, for a part that belongs to the segment before it. */
  readonly hatched?: boolean;
}

/** One bar: a value per series, the text past its end and the lines its tooltip shows. */
export interface BarRow {
  readonly label: string;
  readonly values: readonly number[];
  readonly tip: string;
  readonly tooltip: readonly string[];
}

/** A bar row with its hidden parts at zero; `whole` keeps the total of every part. */
interface ShownRow extends BarRow {
  readonly whole: number;
}

/** The CSS fill of a series' swatch, striped like its bars where they are. */
function swatch(series: BarSeries): string {
  return series.hatched
    ? `repeating-linear-gradient(135deg, ${series.color} 0 2px, ${series.color}59 2px 4px)`
    : series.color;
}

function sum(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

/** Diagonal stripes of `color` over a faint wash of it, as a canvas fill. */
function hatch(document: Document, color: string): CanvasPattern | string {
  const tile = document.createElement('canvas');
  tile.width = tile.height = 6;
  const ctx = tile.getContext('2d');
  if (!ctx) {
    return color;
  }
  ctx.fillStyle = `${color}59`;
  ctx.fillRect(0, 0, 6, 6);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (const offset of [-6, 0, 6]) {
    ctx.moveTo(offset, 6);
    ctx.lineTo(offset + 6, 0);
  }
  ctx.stroke();
  return ctx.createPattern(tile, 'repeat') ?? color;
}

const SINGLE: readonly BarSeries[] = [{ label: '', color: SERIES_COLORS[0] }];

/** Height of one bar's band in pixels; the bar itself is capped thinner. */
const BAND_PX = 34;
const BAR_PX = 20;
/** The far end of a bar is rounded, the end at the axis stays square. */
const ROUNDED_END = { topLeft: 0, bottomLeft: 0, topRight: 4, bottomRight: 4 };
/** Room for the tip text, per character and in total. */
const TIP_CHAR_PX = 6.5;
const TIP_GAP_PX = 6;

/** Room left around a label written inside a segment, in pixels. */
const INSIDE_PAD_PX = 4;

/** Dark text on light fills, white on dark ones, judged by the fill's relative luminance. */
export function inkOn(hex: string): string {
  const [r, g, b] = [1, 3, 5].map((at) => {
    const channel = parseInt(hex.slice(at, at + 2), 16) / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.179 ? '#1b1b1f' : '#ffffff';
}

/** Whether the segment at `index` is the last one drawn in its bar, which gets the rounded end. */
export function endsBar(values: readonly number[], index: number): boolean {
  return values[index] > 0 && values.slice(index + 1).every((value) => value === 0);
}

/** Round axis ends with a whole-number tick step that divides them, per order of magnitude. */
const AXIS_ENDS: readonly (readonly [number, number])[] = [
  [1, 0.2],
  [1.5, 0.5],
  [2, 0.5],
  [2.5, 0.5],
  [3, 1],
  [4, 1],
  [5, 1],
  [6, 2],
  [8, 2],
  [10, 2],
];

/** The smallest round end at or above a count, and the tick step that divides it. */
export function countAxis(value: number): { max: number; step: number } {
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(value, 1)));
  const [end, step] =
    AXIS_ENDS.find(([factor]) => factor * magnitude >= value) ?? AXIS_ENDS[AXIS_ENDS.length - 1];
  return { max: end * magnitude, step: Math.max(1, step * magnitude) };
}

/** Horizontal bars, stacked when there is more than one series, each with its value at the tip. */
@Component({
  selector: 'app-bar-chart',
  imports: [UIChart],
  templateUrl: './bar-chart.component.html',
  styleUrl: './bar-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BarChartComponent {
  private readonly document = inject(DOCUMENT);
  private readonly theme = chartTheme(this.document);

  readonly rows = input.required<readonly BarRow[]>();
  readonly series = input<readonly BarSeries[]>(SINGLE);
  /** What the bars stand for, read out to screen readers before the values. */
  readonly label = input.required<string>();
  /** Caption under the value axis. */
  readonly axis = input<string | null>(null);
  /** Values are percentages from 0 to 100. */
  readonly percent = input(false);
  /** Writes each plain segment's share of its bar inside it, where it fits. */
  readonly inside = input(false);
  /** Figures about the whole chart, written in the legend line. */
  readonly notes = input<readonly string[]>([]);
  /** Hides the legend, for a chart under another one with the same series. */
  readonly bare = input(false);
  /** A name above the bars, for one of several charts in a panel. */
  readonly caption = input<string | null>(null);
  /** Indices of the series switched off in the legend; the value axis fits the rest. */
  readonly hiddenSeries = model<ReadonlySet<number>>(new Set());

  /** The named series of a stacked chart, each with its swatch and whether it is shown. */
  protected readonly legend = computed(() => {
    const hidden = this.hiddenSeries();
    return this.bare() || this.series().length < 2
      ? []
      : this.series()
          .map((series, index) => ({ series, index }))
          .filter(({ series }) => series.label)
          .map(({ series, index }) => ({
            index,
            label: series.label,
            fill: swatch(series),
            shown: !hidden.has(index),
          }));
  });

  /** The bars as drawn: hidden series at zero, and bars with nothing left dropped. */
  private readonly shown = computed<ShownRow[]>(() => {
    const hidden = this.hiddenSeries();
    const rows = this.rows().map((row) => ({
      ...row,
      whole: sum(row.values),
      values: row.values.map((value, index) => (hidden.has(index) ? 0 : value)),
    }));
    return hidden.size === 0 ? rows : rows.filter((row) => sum(row.values) > 0);
  });

  protected readonly height = computed(
    () => `${this.shown().length * BAND_PX + 28 + (this.axis() ? 16 : 0)}px`,
  );

  protected toggle(index: number): void {
    this.hiddenSeries.update((hidden) => {
      const next = new Set(hidden);
      if (!next.delete(index)) {
        next.add(index);
      }
      return next;
    });
  }

  private readonly hatches = new Map<string, CanvasPattern | string>();

  private hatchOf(color: string): CanvasPattern | string {
    let fill = this.hatches.get(color);
    if (fill === undefined) {
      fill = hatch(this.document, color);
      this.hatches.set(color, fill);
    }
    return fill;
  }

  private isEnd(row: number, series: number): boolean {
    return endsBar(this.shown()[row].values, series);
  }

  protected readonly data = computed<ChartData<'bar', number[]>>(() => {
    const rows = this.shown();
    return {
      labels: rows.map((row) => row.label),
      datasets: this.series().map((series, index) => ({
        label: series.label,
        data: rows.map((row) => row.values[index] ?? 0),
        backgroundColor: series.hatched ? this.hatchOf(series.color) : series.color,
        borderColor: this.theme.surface,
        borderWidth: (context: ScriptableContext<'bar'>) =>
          this.isEnd(context.dataIndex, index) ? 0 : { top: 0, right: 2, bottom: 0, left: 0 },
        borderRadius: (context: ScriptableContext<'bar'>) =>
          this.isEnd(context.dataIndex, index) ? ROUNDED_END : 0,
        borderSkipped: false,
        maxBarThickness: BAR_PX,
        stack: 'bar',
      })),
    };
  });

  protected readonly options = computed<ChartOptions<'bar'>>(() => {
    const rows = this.shown();
    const percent = this.percent();
    const axis = this.axis();
    const longestTip = Math.max(0, ...rows.map((row) => row.tip.length));
    const longestBar = Math.max(0, ...rows.map((row) => sum(row.values)));
    const scale =
      percent && this.hiddenSeries().size === 0 ? { max: 100, step: 25 } : countAxis(longestBar);
    return {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      font: { family: this.theme.font },
      layout: { padding: { right: longestTip * TIP_CHAR_PX + TIP_GAP_PX + 4 } },
      interaction: { mode: 'index', axis: 'y', intersect: false },
      scales: {
        x: {
          stacked: true,
          min: 0,
          max: scale.max,
          grid: { color: this.theme.border },
          border: { display: false },
          ticks: {
            ...axisTicks(this.theme),
            stepSize: scale.step,
            callback: (value) => (percent ? `${value} %` : `${value}`),
          },
          title: axis ? axisTitle(this.theme, axis) : undefined,
        },
        y: {
          stacked: true,
          grid: { display: false },
          border: { display: false },
          ticks: { ...axisTicks(this.theme), font: { family: this.theme.font, size: 11 } },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipStyle(this.theme),
          displayColors: false,
          filter: (_item, index) => index === 0,
          callbacks: {
            title: (items) => rows[items[0].dataIndex].label,
            label: (item) => [...rows[item.dataIndex].tooltip],
          },
        },
      },
    };
  });

  /** Each bar's tip text written just past its end, in the text colour. */
  protected readonly plugins: Plugin<'bar'>[] = [
    {
      id: 'tipLabels',
      afterDatasetsDraw: (chart) => {
        const { ctx } = chart;
        const rows = this.shown();
        ctx.save();
        ctx.font = `600 11px ${this.theme.font}`;
        ctx.fillStyle = this.theme.text;
        ctx.textBaseline = 'middle';
        chart.getDatasetMeta(0).data.forEach((element, index) => {
          const end = sum(rows[index].values);
          const x = chart.scales['x'].getPixelForValue(end) + TIP_GAP_PX;
          ctx.fillText(rows[index].tip, x, element.y);
        });
        ctx.restore();
      },
    },
    {
      id: 'insideLabels',
      afterDatasetsDraw: (chart) => {
        if (!this.inside()) {
          return;
        }
        const { ctx } = chart;
        const rows = this.shown();
        ctx.save();
        ctx.font = `600 10px ${this.theme.font}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const series = this.series();
        series.forEach((part, index) => {
          if (part.hatched) {
            return;
          }
          // A hatched part that follows belongs to this segment and shares its label.
          let last = index;
          while (series[last + 1]?.hatched) {
            last++;
          }
          chart.getDatasetMeta(index).data.forEach((element, row) => {
            const values = rows[row].values.slice(index, last + 1);
            const value = sum(values);
            const { base } = element.getProps(['base'], true) as { base: number };
            const x = chart.scales['x'].getPixelForValue(sum(rows[row].values.slice(0, last + 1)));
            const text = `${Math.round((100 * value) / rows[row].whole)} %`;
            if (value <= 0 || x - base < ctx.measureText(text).width + INSIDE_PAD_PX) {
              return;
            }
            ctx.fillStyle = inkOn(part.color);
            ctx.fillText(text, (x + base) / 2, element.y);
          });
        });
        ctx.restore();
      },
    },
  ];

  protected readonly ariaLabel = computed(
    () =>
      `${this.label()}: ${this.shown()
        .map((row) => `${row.label} ${row.tip}`)
        .join(', ')}`,
  );
}
