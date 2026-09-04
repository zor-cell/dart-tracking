import { CheckoutMode } from '../models/checkout-mode';
import { GameMode } from '../models/game-mode';

/** Derived on the server: `abandoned` is what an untouched open game becomes. */
export type GameStatus = 'active' | 'finished' | 'abandoned' | 'discarded';

export interface GameSummaryPlayerDto {
  readonly name: string;
  readonly remaining: number;
  readonly isMe: boolean;
}

export interface GameSummaryDto {
  readonly id: string;
  readonly mode: GameMode;
  readonly checkoutMode: CheckoutMode;
  readonly status: GameStatus;
  readonly players: readonly GameSummaryPlayerDto[];
  readonly winnerIndex: number | null;
  readonly dartCount: number;
  readonly createdAt: string;
  /** Whether this game moves the statistics. */
  readonly counted: boolean;
}
