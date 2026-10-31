import { TrendPointDto } from '../dto/trend-point.dto';

/** Which figure the trend follows across the games. */
export type TrendMetric = 'average' | 'firstNine' | 'checkout';

export const TREND_METRICS: readonly { label: string; value: TrendMetric; unit: string }[] = [
  { label: '3-Dart-Ø', value: 'average', unit: '' },
  { label: 'First-9-Ø', value: 'firstNine', unit: '' },
  { label: 'Checkout', value: 'checkout', unit: ' %' },
];

/** The newest game's share of the trend line; whatever came before keeps the rest. */
export const TREND_WEIGHT = 0.2;

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
  }
}

/** A weighted average up to each game: the newest counts `TREND_WEIGHT`, each one before it
 * that share less again. The checkout weighs its darts, since a game's rate rests on very few. */
export function weightedTrend(
  points: readonly TrendPointDto[],
  metric: TrendMetric,
): (number | null)[] {
  let sum = 0;
  let weight = 0;
  return points.map((point) => {
    const value = trendValue(point, metric);
    const [amount, count] =
      metric === 'checkout'
        ? [point.checkoutHits * 100, point.checkoutAttempts]
        : [value ?? 0, value === null ? 0 : 1];
    // A game without a value leaves the line where it was.
    if (count > 0) {
      sum = TREND_WEIGHT * amount + (1 - TREND_WEIGHT) * sum;
      weight = TREND_WEIGHT * count + (1 - TREND_WEIGHT) * weight;
    }
    return weight === 0 ? null : sum / weight;
  });
}
