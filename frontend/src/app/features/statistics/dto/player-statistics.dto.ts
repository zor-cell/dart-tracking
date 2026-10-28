import { DoubleStatisticsDto, MissDirection } from './double-statistics.dto';
import { ScatterDto } from './scatter.dto';

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
  readonly visits180: number;
  readonly visits100Plus: number;
  readonly legsWithChance: number;
  readonly checkoutAttempts: number;
  readonly checkoutHits: number;
  readonly fields: Readonly<Record<string, number>>;
  readonly heatmap: readonly HeatmapCell[];
  /** Doubles thrown at for a finish, most attempted first. */
  readonly doubles: readonly DoubleStatisticsDto[];
  readonly doubleDistance: number | null;
  readonly doubleDartsLocated: number;
  readonly missDirections: Readonly<Record<MissDirection, number>>;
  /** Mean distance (mm) between two located darts of a scoring visit. */
  readonly grouping: number | null;
  readonly groupingDarts: number;
  readonly scatter: ScatterDto | null;
  /** Points per dart by its place in a scoring visit. */
  readonly dartAverages: readonly (number | null)[];
}
