/** One training without a target: its darts and points per three darts. */
export interface ScoringGameDto {
  readonly gameId: string;
  readonly playedAt: string;
  readonly darts: number;
  readonly average: number;
}
