/** How many darts a visit holds — the same rule as the server's DARTS_PER_TURN. */
export const DARTS_PER_TURN = 3;

/** Points of a called-out field: 20, D20, T20, 25, 50, 0. */
export function labelPoints(label: string): number {
  const multiplier = label.startsWith('T') ? 3 : label.startsWith('D') ? 2 : 1;
  return multiplier * Number(label.replace(/^[DT]/, ''));
}

/** A spot in the replay: the visit, and how many of its darts (dart + 1) are thrown. */
export interface ReplayPosition {
  readonly visit: number;
  readonly dart: number;
}
