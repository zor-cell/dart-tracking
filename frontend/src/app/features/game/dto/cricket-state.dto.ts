import { CricketOptionsDto } from './cricket-options.dto';

export interface CricketPlayerDto {
  /** Marks per target, in the order of `targets`, three at most. */
  readonly marks: readonly number[];
  readonly points: number;
  /** Counted marks per three darts; null before the first dart. */
  readonly marksPerRound: number | null;
  /** Counted marks of the last closed visit; null before it. */
  readonly lastVisit: number | null;
}

export interface CricketStateDto extends CricketOptionsDto {
  /** 20 down to 15, then 25 for the bull. */
  readonly targets: readonly number[];
  /** One per player, in seat order. */
  readonly players: readonly CricketPlayerDto[];
}
