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
    case 'dartsPerLeg':
      return point.legsWon === 0 ? null : point.wonLegDarts / point.legsWon;
  }
}

/** What a game adds to the trend and how much it weighs; rates weigh their attempts. */
function trendShare(point: TrendPointDto, metric: TrendMetric): [amount: number, count: number] {
  switch (metric) {
    case 'checkout':
      return [point.checkoutHits * 100, point.checkoutAttempts];
    case 'dartsPerLeg':
      return [point.wonLegDarts, point.legsWon];
    default: {
      const value = trendValue(point, metric);
      return value === null ? [0, 0] : [value, 1];
    }
  }
}

/** A weighted average up to each game: the newest counts `TREND_WEIGHT`, each one before it
 * that share less again. Rates weigh their attempts, since a game's rate rests on very few. */
export function weightedTrend(
  points: readonly TrendPointDto[],
  metric: TrendMetric,
): (number | null)[] {
  let sum = 0;
  let weight = 0;
  return points.map((point) => {
    const [amount, count] = trendShare(point, metric);
    // A game without a value leaves the line where it was.
    if (count > 0) {
      sum = TREND_WEIGHT * amount + (1 - TREND_WEIGHT) * sum;
      weight = TREND_WEIGHT * count + (1 - TREND_WEIGHT) * weight;
    }
    return weight === 0 ? null : sum / weight;
  });
}
