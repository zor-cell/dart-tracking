import { DartDto } from './dart.dto';

export interface VisitDto {
  readonly playerId: number;
  readonly darts: readonly DartDto[];
  /** Zero for a bust. */
  readonly points: number;
  readonly busted: boolean;
  /** What the thrower still needed after this visit. */
  readonly remaining: number;
}
