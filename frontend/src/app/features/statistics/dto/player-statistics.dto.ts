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
}
