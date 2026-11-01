import { PlayerStatisticsDto } from '../../statistics/dto/player-statistics.dto';
import { GameStateDto } from './game-state.dto';
import { GameStatus } from './game-summary.dto';
import { VisitDto } from './visit.dto';

export interface GameDetailDto {
  readonly game: GameStateDto;
  readonly status: GameStatus;
  readonly createdAt: string;
  readonly finishedAt: string | null;
  /** Seconds of actual play, breaks left out; null for games from before times were kept. */
  readonly playedSeconds: number | null;
  /** Whether the reader set the game up, and so may take it out of the statistics. */
  readonly owned: boolean;
  /** One per player, in seat order. */
  readonly statistics: readonly PlayerStatisticsDto[];
  readonly visits: readonly VisitDto[];
}
