/** Which side of a double a dart missed on, seen with the double turned to the top. */
export type MissDirection = 'short' | 'long' | 'left' | 'right';

/** A located dart at a double, in board mm. */
export type DoubleThrow = readonly [x: number, y: number, hit: boolean];

export interface DoubleStatisticsDto {
  /** Called-out label of the double: D16, or 50 for the bull. */
  readonly label: string;
  readonly attempts: number;
  readonly hits: number;
  /** Mean distance of a located miss from the double, in mm. */
  readonly missDistance: number | null;
  readonly directions: Readonly<Record<MissDirection, number>>;
  readonly throws: readonly DoubleThrow[];
}
