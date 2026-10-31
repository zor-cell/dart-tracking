import { HeatmapCell } from './player-statistics.dto';

export interface DoubleStatisticsDto {
  /** Called-out label of the double: D16, or 50 for the bull. */
  readonly label: string;
  readonly attempts: number;
  readonly hits: number;
  /** Mean distance of a located dart from the double, 0 for a hit, in mm. */
  readonly distance: number | null;
  /** Darts per field they hit, tracked or not, keyed by called-out label. */
  readonly fields: Readonly<Record<string, number>>;
  readonly located: number;
  readonly locatedHits: number;
  /** Where the located darts landed. */
  readonly cells: readonly HeatmapCell[];
}
