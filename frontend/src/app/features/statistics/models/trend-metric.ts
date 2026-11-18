import { CricketGameDto } from '../dto/cricket-game.dto';
import { GameTallyDto } from '../dto/game-tally.dto';
import { ScoringGameDto } from '../dto/scoring-game.dto';
import { TrendPointDto } from '../dto/trend-point.dto';

/** A game the trend chart places on its axis. */
export interface TrendGame {
  readonly gameId: string;
  readonly playedAt: string;
}

/** A figure the trend can follow: its toggle label, value unit, y-axis title and how a game
 * gives it; null where a game has none, such as no checkout chance. */
export interface TrendFigure<T extends TrendGame> {
  readonly label: string;
  readonly value: string;
  readonly unit: string;
  readonly axis: string;
  readonly of: (game: T) => number | null;
  /** Leaves games without the figure off the axis instead of drawing a gap. */
  readonly sparse?: boolean;
}

/** The figures of x01 and elimination. */
export const POINTS_FIGURES: readonly TrendFigure<TrendPointDto>[] = [
  { label: '3-Dart-Ø', value: 'average', unit: '', axis: '3-Dart-Ø', of: (point) => point.average },
  {
    label: 'First-9-Ø',
    value: 'firstNine',
    unit: '',
    axis: 'First-9-Ø',
    of: (point) => point.firstNineAverage,
  },
  {
    label: 'Checkout',
    value: 'checkout',
    unit: ' %',
    axis: $localize`:@@stats.trend.axis.checkout:Checkout-Quote in %`,
    of: (point) =>
      point.checkoutAttempts === 0 ? null : (point.checkoutHits / point.checkoutAttempts) * 100,
  },
  {
    label: $localize`:@@stats.trend.dartsPerLeg:Darts/Leg`,
    value: 'dartsPerLeg',
    unit: '',
    axis: $localize`:@@stats.trend.axis.dartsPerLeg:Darts pro gewonnenem Leg`,
    of: (point) => (point.legsWon === 0 ? null : point.wonLegDarts / point.legsWon),
  },
];

/** The figures of the games at targets. */
export const TARGET_FIGURES: readonly TrendFigure<GameTallyDto>[] = [
  {
    label: $localize`:@@game.scoreboard.hitRate:Quote`,
    value: 'rate',
    unit: ' %',
    axis: $localize`:@@stats.trend.axis.hitRate:Trefferquote in %`,
    of: (game) => (game.darts === 0 ? null : (100 * game.hits) / game.darts),
  },
  {
    label: $localize`:@@stats.targets.distanceShort:Abstand`,
    value: 'distance',
    unit: ' mm',
    axis: $localize`:@@stats.trend.axis.distance:Abstand zum Ziel in mm`,
    of: (game) => game.distance,
  },
];

/** The figures of the free trainings without a target. */
export const SCORING_FIGURES: readonly TrendFigure<ScoringGameDto>[] = [
  { label: '3-Dart-Ø', value: 'average', unit: '', axis: '3-Dart-Ø', of: (game) => game.average },
];

/** The figures of Cricket. */
export const CRICKET_FIGURES: readonly TrendFigure<CricketGameDto>[] = [
  { label: 'MPR', value: 'mpr', unit: '', axis: $localize`:@@stats.cricket.axis.mpr:Marks pro Runde`, of: (game) => game.mpr },
  {
    label: $localize`:@@stats.targets.distanceShort:Abstand`,
    value: 'distance',
    unit: ' mm',
    axis: $localize`:@@stats.cricket.axis.distance:Abstand zur offenen Zahl in mm`,
    of: (game) => game.distance,
  },
];

/** How many games, up to the current one, the form line averages. */
export const TREND_WINDOW = 5;

/** The mean of each value and the ones before it within `TREND_WINDOW`, gaps left out. */
export function rollingAverage(values: readonly (number | null)[]): (number | null)[] {
  return values.map((_, index) => {
    const pooled = values
      .slice(Math.max(0, index - TREND_WINDOW + 1), index + 1)
      .filter((value) => value !== null);
    return pooled.length === 0
      ? null
      : pooled.reduce((sum, value) => sum + value, 0) / pooled.length;
  });
}
