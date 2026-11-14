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

export interface ClockStandingDto {
  readonly variant: 'around_the_clock';
  /** One per player, in seat order. */
  readonly players: readonly ClockPlayerDto[];
}
