/**
 * Client -> server: book one dart, as the field it landed in rather than as
 * points — the server derives its points and the called-out label from that.
 *
 * Sent by any device in the game's room: the camera phone correcting a misread,
 * a scoreboard phone entering the visit by hand. There is no reply of its own —
 * the server applies the change and pushes the new state to the whole room.
 */
export interface RegisterDartDto {
  readonly type: 'register_dart';
  readonly value: number; // sector value, 25 for the bull, 0 for a miss
  readonly multiplier: number; // 0 miss, 1 single, 2 double, 3 triple
}
