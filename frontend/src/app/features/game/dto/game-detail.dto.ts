import { PlayerStatisticsDto } from '../../statistics/dto/player-statistics.dto';
import { GameStateDto } from './game-state.dto';
import { GameStatus } from './game-summary.dto';
import { VisitDto } from './visit.dto';

export interface GameDetailDto {
  readonly game: GameStateDto;
  readonly status: GameStatus;
  readonly createdAt: string;
  readonly finishedAt: string | null;
  /** One per player, in seat order. */
  readonly statistics: readonly PlayerStatisticsDto[];
  readonly visits: readonly VisitDto[];
}
