import { GameCommandDto } from './game-command.dto';

/** Client -> server: book a different field for one dart of the open visit. The
 * dart keeps its place; the replacement is a manual booking, so it has no tip. */
export interface ReplaceDartDto extends GameCommandDto {
  readonly type: 'replace_dart';
  readonly index: number;
  readonly value: number; // sector value, 25 for the bull, 0 for a miss
  readonly multiplier: number; // 0 miss, 1 single, 2 double, 3 triple
}
