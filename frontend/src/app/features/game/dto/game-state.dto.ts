import { GameMode } from '../models/game-mode';
import { PlayerDto } from './player.dto';
import { TurnDto } from './turn.dto';

export interface GameStateDto {
  readonly id: string;
  readonly mode: GameMode;
  readonly players: readonly PlayerDto[];
  readonly currentPlayerIndex: number;
  readonly turns: readonly TurnDto[];
  readonly dartsRemaining: number;
  readonly winnerId: number | null;
}
