export interface DartDto {
  readonly points: number;
  /** Called-out form of the field hit: 20, D20, T20, 25, 50, 0. */
  readonly label: string;
  /**
   * Where the tip landed, `[x, y]` in board millimetres — null for a manually
   * entered dart, whose field is known but whose exact point is not.
   */
  readonly position: readonly [number, number] | null;
}
