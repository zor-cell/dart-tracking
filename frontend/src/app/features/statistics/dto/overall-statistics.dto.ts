import { HeatmapCell } from './player-statistics.dto';

export interface WeekDto {
  /** The Monday the week starts on, as an ISO date. */
  readonly week: string;
  readonly darts: number;
}

export interface DayDto {
  readonly day: string;
  readonly darts: number;
}

export interface RivalDto {
  readonly playerId: string;
  readonly name: string;
  readonly games: number;
  readonly wins: number;
  readonly losses: number;
}

/** Every finished game of any kind: how much, where the darts went, when and against whom. */
export interface OverallStatisticsDto {
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
  /** Darts per called-out label, a miss as 0; the located ones apart, as the heatmaps take them. */
  readonly fields: Readonly<Record<string, number>>;
  readonly locatedFields: Readonly<Record<string, number>>;
  readonly heatmap: readonly HeatmapCell[];
  /** Darts per ring: single (the 25 too), double (the bull too), triple, miss. */
  readonly rings: Readonly<Record<string, number>>;
  /** Oldest first, the weeks without a dart included. */
  readonly weeks: readonly WeekDto[];
  readonly longestStreak: number;
  readonly busiestDay: DayDto | null;
  /** How many different players one has played against. */
  readonly opponents: number;
  /** The opponent met most often. */
  readonly rival: RivalDto | null;
}
