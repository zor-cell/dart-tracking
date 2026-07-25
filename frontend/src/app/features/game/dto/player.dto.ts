export interface PlayerDto {
  readonly id: number;
  readonly name: string;
  readonly remaining: number;
  // Points thrown in the player's most recent visit (null before their first),
  // shown next to them so the auto-advance is easy to verify.
  readonly lastTurn: number | null;
  readonly lastTurnBusted: boolean;
}
