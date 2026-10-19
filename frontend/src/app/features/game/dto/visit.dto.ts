import { DartDto } from './dart.dto';

export interface VisitDto {
  readonly playerId: number;
  readonly darts: readonly DartDto[];
  /** Zero for a bust. */
  readonly points: number;
  readonly busted: boolean;
  /** Points each player still needed after this visit, indexed by player id. */
  readonly standings: readonly number[];
}
