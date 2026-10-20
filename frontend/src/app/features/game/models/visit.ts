/** How many darts a visit holds — the same rule as the server's DARTS_PER_TURN. */
export const DARTS_PER_TURN = 3;

/** A spot in the replay: the visit, and how many of its darts (dart + 1) are thrown. */
export interface ReplayPosition {
  readonly visit: number;
  readonly dart: number;
}
