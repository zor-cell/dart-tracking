/**
 * Client -> server: the changes a device asks the server to make.
 *
 * Every device in the game's room may send these — the camera phone correcting
 * a misread, a scoreboard phone entering the visit by hand. There is no reply
 * of their own: the server applies the change and pushes the new `game_state`
 * to the whole room.
 *
 * Grouped in one file because they are always used as the union below.
 */

/** Book one dart, as the field it landed in — the server derives its points and
 * the called-out label from that. */
export interface RegisterDartCommand {
  readonly type: 'register_dart';
  readonly value: number; // sector value, 25 for the bull, 0 for a miss
  readonly multiplier: number; // 0 miss, 1 single, 2 double, 3 triple
}

/** Step back one action — a dart, or the switch to the current player. */
export interface UndoCommand {
  readonly type: 'undo';
}

/** End the visit and hand over to the next player. */
export interface NextPlayerCommand {
  readonly type: 'next_player';
}