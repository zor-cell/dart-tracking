/** A located dart at a double, in board mm. */
export type DoubleThrow = readonly [x: number, y: number, hit: boolean];

export interface DoubleStatisticsDto {
  /** Called-out label of the double: D16, or 50 for the bull. */
  readonly label: string;
  readonly attempts: number;
  readonly hits: number;
  /** Mean distance of a located dart from the double, 0 for a hit, in mm. */
  readonly distance: number | null;
  /** Darts per field they hit, tracked or not, keyed by called-out label. */
  readonly fields: Readonly<Record<string, number>>;
  readonly throws: readonly DoubleThrow[];
}
