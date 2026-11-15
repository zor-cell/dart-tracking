import { GameStateDto } from './game-state.dto';

/** A new game's state; an anonymous one carries the token that can claim it later. */
export interface GameCreatedDto extends GameStateDto {
  readonly claimToken: string | null;
}
