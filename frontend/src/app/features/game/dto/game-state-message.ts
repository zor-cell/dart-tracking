import { GameStateDto } from './game-state.dto';

/**
 * Server -> client: authoritative game state.
 *
 * Pushed right after connecting (so a (re-)connecting client is in sync —
 * there is no separate WS-side session to persist, `gameId` in the URL is the
 * only thing tying the socket to a game) and, once real dart scoring lands,
 * again after every scored throw.
 */
export interface GameStateMessage {
  readonly type: 'game_state';
  readonly state: GameStateDto;
}
