export interface GameKillsDto {
  readonly gameId: string;
  readonly playedAt: string;
  /** Resets in Elimination, lives taken from others in Killer. */
  readonly kills: number;
  /** Times sent back, or lives lost, the own darts included. */
  readonly losses: number;
  readonly won: boolean;
  readonly darts: number;
}
