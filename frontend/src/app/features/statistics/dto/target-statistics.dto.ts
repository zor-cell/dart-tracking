import { FieldTallyDto } from './field-tally.dto';
import { GameTallyDto } from './game-tally.dto';
import { TargetTallyDto } from './target-tally.dto';

/** The darts thrown at named fields, in one tally, per field and game by game. */
export interface TargetStatisticsDto extends TargetTallyDto {
  /** Sorted by number, the bull last. */
  readonly fields: readonly FieldTallyDto[];
  /** Oldest first. */
  readonly games: readonly GameTallyDto[];
  /** Mean darts of the games the player got through; null without one. */
  readonly dartsToFinish: number | null;
  readonly best: GameTallyDto | null;
}
