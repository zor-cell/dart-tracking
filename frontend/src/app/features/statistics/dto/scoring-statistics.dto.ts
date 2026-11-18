import { HitPatternDto } from './hit-pattern.dto';
import { ScoringGameDto } from './scoring-game.dto';
import { VisitRefDto } from './visit-ref.dto';

/** The trainings without a target: their points, visit by visit and game by game. */
export interface ScoringStatisticsDto extends HitPatternDto {
  readonly darts: number;
  readonly average: number;
  readonly bestVisit: number;
  readonly bestVisitAt: VisitRefDto | null;
  readonly visits180: number;
  readonly visits140Plus: number;
  readonly visits100Plus: number;
  readonly visits60Plus: number;
  /** Visits by points. */
  readonly visitScores: Readonly<Record<string, number>>;
  /** Oldest first. */
  readonly games: readonly ScoringGameDto[];
}
