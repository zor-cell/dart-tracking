export interface PlayerDto {
  readonly id: number;
  readonly name: string;
  readonly identityId: string;
  readonly remaining: number;
  /** Points per three darts in this game; null before the first dart. */
  readonly average: number | null;
  /** Points of the last closed visit; null before it. */
  readonly lastVisit: number | null;
}
