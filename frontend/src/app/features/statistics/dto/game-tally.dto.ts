import { TargetTallyDto } from './target-tally.dto';

export interface GameTallyDto extends TargetTallyDto {
  readonly gameId: string;
  readonly playedAt: string;
  /** Whether the player got through every target of the game. */
  readonly through: boolean;
}
