/** One card of the scoreboard: the number is whatever the variant counts. */
export interface ScoreboardEntry {
  readonly id: number;
  readonly name: string;
  readonly score: number;
  /** Points per three darts in this game; null before the first dart. */
  readonly average: number | null;
  /** Points of the last closed visit; null before it. */
  readonly lastVisit: number | null;
  /** Whether the player alone is closest to the finish. */
  readonly leading: boolean;
  /** Whether the latest visit sent the player back to zero. */
  readonly reset: boolean;
  /** How often the player has sent another back to zero; null outside elimination. */
  readonly eliminations: number | null;
}
