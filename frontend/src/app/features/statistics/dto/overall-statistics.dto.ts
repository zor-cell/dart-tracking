import { HitPatternDto } from './hit-pattern.dto';

export interface WeekDto {
  /** The Monday the week starts on, as an ISO date. */
  readonly week: string;
  readonly darts: number;
}

export interface DayDto {
  readonly day: string;
  readonly darts: number;
}

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
  /** Games per variant. */
  readonly variants: Readonly<Record<string, number>>;
  /** Darts per ring: single (the 25 too), double (the bull too), triple, miss. */
  readonly rings: Readonly<Record<string, number>>;
  /** Oldest first, the weeks without a dart included. */
  readonly weeks: readonly WeekDto[];
  readonly longestStreak: number;
  readonly busiestDay: DayDto | null;
}
