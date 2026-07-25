import { GameMode } from '../models/game-mode';
import { CheckoutMode } from '../models/checkout-mode';
import { PlayerDto } from './player.dto';
import { TurnDto } from './turn.dto';

export interface GameStateDto {
  readonly id: string;
  readonly mode: GameMode;
  readonly checkoutMode: CheckoutMode;
  readonly players: readonly PlayerDto[];
  readonly currentPlayerIndex: number;
  readonly turns: readonly TurnDto[];
  readonly dartsRemaining: number;
  readonly canUndo: boolean;
  readonly winnerId: number | null;
  readonly checkout: readonly string[] | null;
}
