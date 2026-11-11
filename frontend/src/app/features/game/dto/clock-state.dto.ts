import { ClockOptionsDto } from './clock-options.dto';

export interface ClockPlayerDto {
  /** The number to hit next, 25 for the bull; null once through. */
  readonly target: number | null;
  /** Targets already passed. */
  readonly done: number;
  readonly hits: number;
  readonly darts: number;
  /** Targets the last closed visit moved on; null before it. */
  readonly lastVisit: number | null;
}

export interface ClockStateDto extends ClockOptionsDto {
  /** One per player, in seat order. */
  readonly players: readonly ClockPlayerDto[];
}
