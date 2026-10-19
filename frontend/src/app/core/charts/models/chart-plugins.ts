import type { Chart, Plugin } from 'chart.js';

/** Colours and font every chart takes from the PrimeNG theme. */
export interface ChartTheme {
  readonly text: string;
  readonly muted: string;
  readonly grid: string;
  readonly surface: string;
  readonly border: string;
  readonly font: string;
}

/** Reads the theme tokens once; Chart.js needs plain colour values, not CSS variables. */
export function chartTheme(document: Document): ChartTheme {
  const root = getComputedStyle(document.documentElement);
  const token = (name: string, fallback: string) => root.getPropertyValue(name).trim() || fallback;
  return {
    text: token('--p-text-color', '#374151'),
    muted: token('--p-text-muted-color', '#6b7280'),
    grid: '#e7e6e2',
    surface: token('--p-content-background', '#ffffff'),
    border: token('--p-content-border-color', '#e5e7eb'),
    font: getComputedStyle(document.body).fontFamily,
  };
}

/** Smallest vertical distance between two end labels, in pixels. */
const END_LABEL_GAP = 13;

/** A dashed vertical line through the hovered index. */
export const crosshairPlugin: Plugin<'line'> = {
  id: 'crosshair',
  afterDatasetsDraw(chart: Chart<'line'>) {
    const active = chart.tooltip?.getActiveElements() ?? [];
    if (active.length === 0) {
      return;
    }
    const { ctx, chartArea } = chart;
    const x = active[0].element.x;
    ctx.save();
    ctx.strokeStyle = '#9ca3af';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  },
};

/** Writes each series' name and last value next to its line end, pushed apart where they collide. */
export const endLabelsPlugin: Plugin<'line'> = {
  id: 'endLabels',
  afterDatasetsDraw(chart: Chart<'line'>) {
    const { ctx, chartArea } = chart;
    const labels = chart.data.datasets
      .map((dataset, index) => {
        // The last value drawn so far: a series cut short ends in nulls.
        let at = dataset.data.length - 1;
        while (at >= 0 && dataset.data[at] === null) {
          at--;
        }
        const point = chart.getDatasetMeta(index).data[at];
        const raw = dataset.data[at];
        const value = typeof raw === 'object' && raw !== null && 'y' in raw ? raw.y : raw;
        return point ? { y: point.y, text: `${dataset.label} ${value}` } : null;
      })
      .filter((label) => label !== null)
      .sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i++) {
      labels[i].y = Math.max(labels[i].y, labels[i - 1].y + END_LABEL_GAP);
    }
    ctx.save();
    ctx.font = `10.5px ${chart.options.font?.family ?? 'sans-serif'}`;
    ctx.fillStyle = (chart.options.plugins?.legend?.labels?.color as string) ?? '#374151';
    ctx.textBaseline = 'middle';
    for (const label of labels) {
      ctx.fillText(label.text, chartArea.right + 6, label.y);
    }
    ctx.restore();
  },
};

/** Writes the `count` of a merged point inside its dot, for points that stand for more than one. */
export const countLabelsPlugin: Plugin<'scatter'> = {
  id: 'countLabels',
  afterDatasetsDraw(chart: Chart<'scatter'>) {
    const { ctx } = chart;
    ctx.save();
    ctx.font = `600 9px ${chart.options.font?.family ?? 'sans-serif'}`;
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    chart.data.datasets.forEach((dataset, index) => {
      chart.getDatasetMeta(index).data.forEach((element, point) => {
        const count = (dataset.data[point] as { count?: number } | undefined)?.count ?? 1;
        if (count > 1) {
          ctx.fillText(String(count), element.x, element.y + 0.5);
        }
      });
    });
    ctx.restore();
  },
};

/** A dashed vertical line at the x index `index()` names; nothing while it is null. */
export function indexMarkerPlugin(index: () => number | null): Plugin<'line'> {
  return {
    id: 'indexMarker',
    afterDatasetsDraw(chart: Chart<'line'>) {
      const at = index();
      if (at === null) {
        return;
      }
      const { ctx, chartArea } = chart;
      const x = chart.scales['x'].getPixelForValue(at);
      ctx.save();
      ctx.strokeStyle = '#6b7280';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };
}
