import { TrendPointDto } from '../dto/trend-point.dto';

/** Which figure the trend follows across the games. */
export type TrendMetric = 'average' | 'firstNine' | 'checkout' | 'dartsPerLeg';

/** Each figure with its toggle label, value unit and y-axis title. */
export const TREND_METRICS: readonly {
  label: string;
  value: TrendMetric;
  unit: string;
  axis: string;
}[] = [
  { label: '3-Dart-Ø', value: 'average', unit: '', axis: '3-Dart-Ø' },
  { label: 'First-9-Ø', value: 'firstNine', unit: '', axis: 'First-9-Ø' },
  {
    label: 'Checkout',
    value: 'checkout',
    unit: ' %',
    axis: $localize`:@@stats.trend.axis.checkout:Checkout-Quote in %`,
  },
  {
    label: $localize`:@@stats.trend.dartsPerLeg:Darts/Leg`,
    value: 'dartsPerLeg',
    unit: '',
    axis: $localize`:@@stats.trend.axis.dartsPerLeg:Darts pro gewonnenem Leg`,
  },
];

/** How many games, up to the current one, the trend line averages. */
export const TREND_WINDOW = 5;

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
    case 'dartsPerLeg':
      return point.legsWon === 0 ? null : point.wonLegDarts / point.legsWon;
  }
}

/** The mean of each game's value and the ones before it within `TREND_WINDOW`, games without
 * a value left out. */
export function rollingTrend(
  points: readonly TrendPointDto[],
  metric: TrendMetric,
): (number | null)[] {
  const values = points.map((point) => trendValue(point, metric));
  return values.map((_, index) => {
    const pooled = values
      .slice(Math.max(0, index - TREND_WINDOW + 1), index + 1)
      .filter((value) => value !== null);
    return pooled.length === 0
      ? null
      : pooled.reduce((sum, value) => sum + value, 0) / pooled.length;
  });
}
