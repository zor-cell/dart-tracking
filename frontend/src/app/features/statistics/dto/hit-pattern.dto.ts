/** A 2 mm cell's centre in board millimetres (x right, y up, origin at the bullseye) and its tips. */
export type HeatmapCell = readonly [x: number, y: number, count: number];

/** Where the darts of a statistics view landed. */
export interface HitPatternDto {
  /** Darts per called-out label, a miss as 0. */
  readonly fields: Readonly<Record<string, number>>;
  /** Located darts per field, the ones the heatmap draws. */
  readonly locatedFields: Readonly<Record<string, number>>;
  readonly heatmap: readonly HeatmapCell[];
}
