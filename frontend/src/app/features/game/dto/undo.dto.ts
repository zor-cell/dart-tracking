import { GameCommandDto } from './game-command.dto';

/** Client -> server: step back one action — a dart, or the switch to the
 * current player. */
export interface UndoDto extends GameCommandDto {
  readonly type: 'undo';
}
