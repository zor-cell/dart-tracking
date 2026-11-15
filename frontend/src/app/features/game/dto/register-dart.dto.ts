import { GameCommandDto } from './game-command.dto';

/**
 * Client -> server: book one dart as the field it landed in, from any device in
 * the room; the new state arrives as the `game_state` push.
 */
export interface RegisterDartDto extends GameCommandDto {
  readonly type: 'register_dart';
  readonly value: number; // sector value, 25 for the bull, 0 for a miss
  readonly multiplier: number; // 0 miss, 1 single, 2 double, 3 triple
}
