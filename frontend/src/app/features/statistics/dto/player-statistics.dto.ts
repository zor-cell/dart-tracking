/** Board millimetres: x right, y up, origin at the bullseye. */
export type HeatmapPoint = readonly [number, number];

export interface PlayerStatisticsDto {
  readonly legs: number;
  readonly legsWon: number;
  readonly darts: number;
  readonly points: number;
  readonly average: number;
  readonly bestVisit: number;
  readonly visits180: number;
  readonly visits100Plus: number;
  readonly checkoutChances: number;
  readonly doubleAttempts: number;
  readonly doubleHits: number;
  readonly heatmap: readonly HeatmapPoint[];
}
