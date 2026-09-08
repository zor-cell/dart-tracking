/** Where the id of the game this device left open lives between page loads. */
export const ACTIVE_GAME_KEY = 'dart-tracking.gameId';

/** Whether a game is open, readable without waking the game service — the root
 * route decides on it and must not pull the socket into the initial bundle. */
export function hasActiveGame(): boolean {
  return localStorage.getItem(ACTIVE_GAME_KEY) !== null;
}
