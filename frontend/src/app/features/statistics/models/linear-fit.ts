import { SERIES_COLORS } from '../../../core/charts/models/series-colors';
import type { TrendLegendEntry } from '../components/trend-legend/trend-legend.component';

/** Colour of the fitted line in every trend chart. */
export const FIT_COLOR = SERIES_COLORS[7];

/** The least-squares line through `values` by their place, drawn from the first value to the
 * last; null outside that span and everywhere with fewer than two values. */
export function linearFit(values: readonly (number | null)[]): (number | null)[] {
  const known = values.flatMap((value, x) => (value === null ? [] : [[x, value] as const]));
  if (known.length < 2) {
    return values.map(() => null);
  }
  const n = known.length;
  const meanX = known.reduce((sum, [x]) => sum + x, 0) / n;
  const meanY = known.reduce((sum, [, y]) => sum + y, 0) / n;
  const spread = known.reduce((sum, [x]) => sum + (x - meanX) ** 2, 0);
  const slope =
    spread === 0 ? 0 : known.reduce((sum, [x, y]) => sum + (x - meanX) * (y - meanY), 0) / spread;
  const [first, last] = [known[0][0], known[n - 1][0]];
  return values.map((_, x) => (x < first || x > last ? null : meanY + slope * (x - meanX)));
}

/** The least-squares line through `values` at the positions `xs`, as its two ends at the first
 * and last known value; empty with fewer than two. */
export function linearFitOver(
  xs: readonly number[],
  values: readonly (number | null)[],
): { x: number; y: number }[] {
  const known = xs.flatMap((x, index) => {
    const value = values[index];
    return value === null || value === undefined ? [] : [[x, value] as const];
  });
  if (known.length < 2) {
    return [];
  }
  const n = known.length;
  const meanX = known.reduce((sum, [x]) => sum + x, 0) / n;
  const meanY = known.reduce((sum, [, y]) => sum + y, 0) / n;
  const spread = known.reduce((sum, [x]) => sum + (x - meanX) ** 2, 0);
  const slope =
    spread === 0 ? 0 : known.reduce((sum, [x, y]) => sum + (x - meanX) * (y - meanY), 0) / spread;
  const at = (x: number) => ({ x, y: meanY + slope * (x - meanX) });
  return [at(known[0][0]), at(known[n - 1][0])];
}

/** The fitted line's switch in a trend legend; it is what the charts call the trend. */
export const FIT_LEGEND: TrendLegendEntry = {
  key: 'trend',
  label: $localize`:@@stats.tab.trend:Trend`,
  swatch: 'line',
  color: FIT_COLOR,
  hint: $localize`:@@stats.trend.fitHint:Die Gerade, die am besten durch alle Spiele des Zeitraums passt: steigt oder fällt der Wert insgesamt?`,
};

/** `hidden` with `part` switched: shown again if it was hidden, hidden otherwise. */
export function toggled<T>(hidden: ReadonlySet<T>, part: T): ReadonlySet<T> {
  const next = new Set(hidden);
  if (!next.delete(part)) {
    next.add(part);
  }
  return next;
}
