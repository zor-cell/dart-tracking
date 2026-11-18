import { CricketGameDto } from './cricket-game.dto';
import { HitPatternDto } from './hit-pattern.dto';
import { VisitRefDto } from './visit-ref.dto';

/** Cricket over the selected games, in one tally and game by game. */
export interface CricketStatisticsDto extends HitPatternDto {
  readonly darts: number;
  readonly marks: number;
  readonly mpr: number | null;
  readonly distance: number | null;
  readonly gamesWithOpponent: number;
  readonly wins: number;
  /** Darts that marked nothing. */
  readonly empty: number;
  /** Visits by the marks they counted, keyed by the marks. */
  readonly visits: Readonly<Record<string, number>>;
  readonly bestVisit: number;
  readonly bestVisitAt: VisitRefDto | null;
  readonly favouriteVisit: number | null;
  /** Oldest first. */
  readonly games: readonly CricketGameDto[];
}
