import { GameCommandDto } from './game-command.dto';

/** Client -> server: end the visit and hand over to the next player. */
export interface NextPlayerDto extends GameCommandDto {
  readonly type: 'next_player';
}
