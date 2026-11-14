import { GameKillsDto } from './game-kills.dto';

export interface KillStatisticsDto {
  readonly kills: number;
  readonly losses: number;
  readonly wins: number;
  /** Darts thrown in the counted games. */
  readonly darts: number;
  /** Oldest first. */
  readonly games: readonly GameKillsDto[];
  /** The game with the most kills; null without a kill. */
  readonly most: GameKillsDto | null;
}
