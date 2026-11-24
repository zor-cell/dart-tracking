import { ActivityDto } from './activity.dto';
import { HitPatternDto } from './hit-pattern.dto';

/** Every finished game of any kind: how much, where the darts went and when. */
export interface OverallStatisticsDto extends HitPatternDto {
  readonly games: number;
  readonly darts: number;
  /** From setting each game up to its end, summed. */
  readonly seconds: number;
  readonly gamesWithOpponent: number;
  readonly wins: number;
  readonly misses: number;
  readonly located: number;
  /** Darts per ring: single (the 25 too), double (the bull too), triple, miss. */
  readonly rings: Readonly<Record<string, number>>;
  /** Null without a game. */
  readonly activity: ActivityDto | null;
}
