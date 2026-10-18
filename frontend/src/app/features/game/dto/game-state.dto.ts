import { GameMode } from '../models/game-mode';
import { CheckoutMode } from '../models/checkout-mode';
import { GameVariant } from '../models/game-variant';
import { DartDto } from './dart.dto';
import { PlayerDto } from './player.dto';
import { TurnDto } from './turn.dto';

/**
 * The authoritative game state — both the answer to an HTTP call and the message
 * pushed over the socket. One schema rather than a payload wrapped in a message,
 * so the state looks the same however it arrived.
 */
export interface GameStateDto {
  readonly type: 'game_state';
  readonly id: string;
  readonly revision: number;
  readonly mode: GameMode;
  readonly variant: GameVariant;
  readonly checkoutMode: CheckoutMode;
  readonly players: readonly PlayerDto[];
  readonly currentPlayerIndex: number;
  readonly turns: readonly TurnDto[];
  /** Darts the camera located after a win or bust closed the open visit; they score nothing yet. */
  readonly shadowDarts: readonly DartDto[];
  readonly dartsRemaining: number;
  readonly canUndo: boolean;
  readonly winnerId: number | null;
  readonly checkout: readonly string[] | null;
  readonly elimination: readonly string[] | null;
  readonly evaluationEnabled: boolean;
  /** Whether a device that left the game open should still be put back into it. */
  readonly resumable: boolean;
}
