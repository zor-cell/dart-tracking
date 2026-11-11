import { CheckoutMode } from '../models/checkout-mode';
import { GameMode } from '../models/game-mode';
import { GameVariant } from '../models/game-variant';

/** Derived on the server: `abandoned` is what an untouched open game becomes. */
export type GameStatus = 'active' | 'finished' | 'abandoned' | 'discarded';

export interface GameSummaryPlayerDto {
  readonly name: string;
  readonly remaining: number | null;
  readonly isMe: boolean;
}

export interface GameSummaryDto {
  readonly id: string;
  readonly mode: GameMode | null;
  readonly variant: GameVariant;
  readonly checkoutMode: CheckoutMode | null;
  readonly status: GameStatus;
  readonly players: readonly GameSummaryPlayerDto[];
  readonly winnerIndex: number | null;
  readonly dartCount: number;
  readonly createdAt: string;
  /** Whether this game moves the statistics. */
  readonly counted: boolean;
}
