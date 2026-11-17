import { DartDto } from './dart.dto';
import { GameSettingsDto } from './game-settings.dto';
import { GameStandingDto } from './game-standing.dto';
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
  readonly settings: GameSettingsDto;
  readonly players: readonly PlayerDto[];
  readonly currentPlayerIndex: number;
  readonly turns: readonly TurnDto[];
  /** Darts the camera located after a win or bust closed the open visit; they score nothing yet. */
  readonly shadowDarts: readonly DartDto[];
  readonly dartsRemaining: number;
  readonly winnerId: number | null;
  /** A race's places so far, best first; empty outside the race variants. */
  readonly places: readonly number[];
  /** Who reached the goal: placed, or finished in the round under way. */
  readonly finisherIds: readonly number[];
  /** Who sits out a tiebreak between the players ahead of them. */
  readonly waitingIds: readonly number[];
  readonly checkout: readonly string[] | null;
  readonly setup: SetupDto | null;
  readonly elimination: readonly string[] | null;
  /** Where everyone stands in a variant with own rules; null for the points variants. */
  readonly standing: GameStandingDto | null;
  readonly evaluationEnabled: boolean;
  /** Whether the camera books nothing for now; the keypad still does. */
  readonly trackingPaused: boolean;
  /** Whether the room has taken the win, which every device then shows as over. */
  readonly winConfirmed: boolean;
  /** Whether a game nobody wins was ended by hand. */
  readonly ended: boolean;
  /** Whether a device that left the game open should still be put back into it. */
  readonly resumable: boolean;
}
