import { TrendPointDto } from '../dto/trend-point.dto';

/** Which figure the trend follows across the games. */
export type TrendMetric = 'average' | 'firstNine' | 'checkout' | 'grouping';

export const TREND_METRICS: readonly { label: string; value: TrendMetric; unit: string }[] = [
  { label: '3-Dart-Ø', value: 'average', unit: '' },
  { label: 'First 9', value: 'firstNine', unit: '' },
  { label: 'Checkout', value: 'checkout', unit: ' %' },
  { label: 'Pfeilabstand', value: 'grouping', unit: ' mm' },
];

/** Games the running line takes together. */
export const TREND_WINDOW = 10;

/** A game's value; null where it has none, such as no checkout chance. */
export function trendValue(point: TrendPointDto, metric: TrendMetric): number | null {
  switch (metric) {
    case 'average':
      return point.average;
    case 'firstNine':
      return point.firstNineAverage;
    case 'checkout':
      return point.checkoutAttempts === 0
        ? null
        : (point.checkoutHits / point.checkoutAttempts) * 100;
    case 'grouping':
      return point.grouping;
  }
}

/** The value over the last `TREND_WINDOW` games up to each game. The checkout pools its
 * darts, since a game's rate rests on very few; the others take the games' mean. */
export function runningTrend(
  points: readonly TrendPointDto[],
  metric: TrendMetric,
): (number | null)[] {
  return points.map((_, index) => {
    const window = points.slice(Math.max(0, index - TREND_WINDOW + 1), index + 1);
    if (metric === 'checkout') {
      const attempts = window.reduce((sum, point) => sum + point.checkoutAttempts, 0);
      const hits = window.reduce((sum, point) => sum + point.checkoutHits, 0);
      return attempts === 0 ? null : (hits / attempts) * 100;
    }
    const values = window.flatMap((point) => trendValue(point, metric) ?? []);
    return values.length === 0
      ? null
      : values.reduce((sum, value) => sum + value, 0) / values.length;
  });
}
