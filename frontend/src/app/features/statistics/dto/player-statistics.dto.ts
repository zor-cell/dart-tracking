import { FieldTallyDto } from './field-tally.dto';
import { HitPatternDto } from './hit-pattern.dto';
import { ScatterDto } from './scatter.dto';
import { VisitRefDto } from './visit-ref.dto';

export interface PlayerStatisticsDto extends HitPatternDto {
  readonly legs: number;
  readonly legsWon: number;
  /** Legs against someone else, and those of them won. */
  readonly duelLegs: number;
  readonly duelLegsWon: number;
  /** The fewest darts a won leg took, and where it was finished. */
  readonly fewestDarts: number | null;
  readonly fewestDartsAt: VisitRefDto | null;
  readonly darts: number;
  /** Darts per won leg; null without one. */
  readonly dartsPerLeg: number | null;
  readonly points: number;
  readonly average: number;
  readonly firstNineAverage: number;
  readonly bestVisit: number;
  /** Points of the best visit that won a leg, 0 without one. */
  readonly highestFinish: number;
  /** Where each was first thrown, the oldest game on a tie. */
  readonly bestVisitAt: VisitRefDto | null;
  readonly highestFinishAt: VisitRefDto | null;
  /** The scoring visit thrown most often; null without one. */
  readonly favouriteVisit: number | null;
  /** The finish thrown most often; null without a won leg. */
  readonly favouriteFinish: number | null;
  /** Unbusted visits by their points, misses included, keyed by the points. */
  readonly visitScores: Readonly<Record<string, number>>;
  /** Visits reaching each score; every band includes the higher ones. */
  readonly visits180: number;
  readonly visits140Plus: number;
  readonly visits100Plus: number;
  readonly visits60Plus: number;
  readonly checkoutAttempts: number;
  readonly checkoutHits: number;
  /** Visits begun with a finish in reach, and those of them that busted. */
  readonly finishVisits: number;
  readonly busts: number;
  /** Doubles thrown at for a finish, most attempted first. */
  readonly doubles: readonly FieldTallyDto[];
  readonly doubleDistance: number | null;
  /** Mean distance (mm) between two located darts of a scoring visit. */
  readonly grouping: number | null;
  readonly groupingDarts: number;
  /** Darts thrown in scoring visits, located or not. */
  readonly scoringDarts: number;
  readonly scatter: ScatterDto | null;
  /** Points per dart by its place in a scoring visit. */
  readonly dartAverages: readonly (number | null)[];
}
