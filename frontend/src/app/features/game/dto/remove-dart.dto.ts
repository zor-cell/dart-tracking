import { GameCommandDto } from './game-command.dto';

/** Client -> server: take one dart out of the open visit, by its position in it. */
export interface RemoveDartDto extends GameCommandDto {
  readonly type: 'remove_dart';
  readonly index: number;
}
