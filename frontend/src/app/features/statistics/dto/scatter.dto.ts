/** How the darts of a visit spread around each other, as an ellipse in board mm. */
export interface ScatterDto {
  /** Standard deviation along the wider and the narrower axis. */
  readonly major: number;
  readonly minor: number;
  /** Degrees of the wider axis, counter-clockwise from +x. */
  readonly angle: number;
}
