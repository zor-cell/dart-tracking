import { DoubleStatisticsDto } from './double-statistics.dto';
import { ScatterDto } from './scatter.dto';
import { VisitRefDto } from './visit-ref.dto';

/** A 2 mm cell's centre in board millimetres (x right, y up, origin at the bullseye) and its tips. */
export type HeatmapCell = readonly [x: number, y: number, count: number];

export interface PlayerStatisticsDto {
  readonly legs: number;
  readonly legsWon: number;
  readonly darts: number;
  readonly points: number;
  readonly average: number;
  readonly firstNineAverage: number;
  readonly bestVisit: number;
  /** Points of the best visit that won a leg, 0 without one. */
  readonly highestFinish: number;
  /** Where each was first thrown, the oldest game on a tie. */
  readonly bestVisitAt: VisitRefDto | null;
  readonly highestFinishAt: VisitRefDto | null;
  /** The scoring visit thrown most often; null without one. */
  readonly favouriteVisit: number | null;
  /** Visits reaching each score; every band includes the higher ones. */
  readonly visits180: number;
  readonly visits140Plus: number;
  readonly visits100Plus: number;
  readonly visits60Plus: number;
  readonly checkoutAttempts: number;
  readonly checkoutHits: number;
  readonly fields: Readonly<Record<string, number>>;
  /** Located darts per field, the ones the heatmap draws. */
  readonly locatedFields: Readonly<Record<string, number>>;
  readonly heatmap: readonly HeatmapCell[];
  /** Doubles thrown at for a finish, most attempted first. */
  readonly doubles: readonly DoubleStatisticsDto[];
  readonly doubleDistance: number | null;
  /** Mean distance (mm) between two located darts of a scoring visit. */
  readonly grouping: number | null;
  readonly groupingDarts: number;
  /** Darts thrown in scoring visits, located or not. */
  readonly scoringDarts: number;
  readonly scatter: ScatterDto | null;
  /** Points per dart by its place in a scoring visit. */
  readonly dartAverages: readonly (number | null)[];
}
