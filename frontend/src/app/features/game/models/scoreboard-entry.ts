/** One card of the scoreboard: the number is whatever the variant counts. */
export interface ScoreboardEntry {
  readonly id: number;
  readonly name: string;
  readonly score: number;
}
