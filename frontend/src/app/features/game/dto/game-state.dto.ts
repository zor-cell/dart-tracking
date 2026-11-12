import { GameMode } from '../models/game-mode';
import { CheckoutMode } from '../models/checkout-mode';
import { GameVariant } from '../models/game-variant';
import { EliminationKill } from '../models/variant-options';
import { ClockStateDto } from './clock-state.dto';
import { CricketStateDto } from './cricket-state.dto';
import { DartDto } from './dart.dto';
import { KillerStateDto } from './killer-state.dto';
import { PlayerDto } from './player.dto';
import { SetupDto } from './setup.dto';
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
  /** The points variants' starting score and finish; null for the others. */
  readonly mode: GameMode | null;
  readonly variant: GameVariant;
  readonly checkoutMode: CheckoutMode | null;
  /** Which darts reset in elimination; null for the other variants. */
  readonly eliminationKill: EliminationKill | null;
  readonly players: readonly PlayerDto[];
  readonly currentPlayerIndex: number;
  readonly turns: readonly TurnDto[];
  /** Darts the camera located after a win or bust closed the open visit; they score nothing yet. */
  readonly shadowDarts: readonly DartDto[];
  readonly dartsRemaining: number;
  readonly canUndo: boolean;
  readonly winnerId: number | null;
  readonly checkout: readonly string[] | null;
  readonly setup: SetupDto | null;
  readonly elimination: readonly string[] | null;
  /** The standing of the variant that is played; null for the others. */
  readonly cricket: CricketStateDto | null;
  readonly killer: KillerStateDto | null;
  readonly aroundTheClock: ClockStateDto | null;
  readonly evaluationEnabled: boolean;
  /** Whether the camera books nothing for now; the keypad still does. */
  readonly trackingPaused: boolean;
  /** Whether the room has taken the win, which every device then shows as over. */
  readonly winConfirmed: boolean;
  /** Whether a device that left the game open should still be put back into it. */
  readonly resumable: boolean;
}
