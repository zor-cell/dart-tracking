export interface PlayerDto {
  readonly id: number;
  readonly name: string;
  readonly identityId: string;
  /** Points still needed in the points variants; null in the others. */
  readonly remaining: number | null;
  /** Points per three darts in this game; null before the first dart. */
  readonly average: number | null;
  /** Points of the last closed visit; null before it. */
  readonly lastVisit: number | null;
  /** Whether the latest visit sent this player back to zero (elimination). */
  readonly justReset: boolean;
  /** How often the player has sent another back to zero (elimination). */
  readonly eliminations: number;
}
