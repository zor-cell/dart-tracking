/** Darts at a target; the rates stay pairs, so the view can weigh them. */
export interface TargetTallyDto {
  readonly darts: number;
  readonly hits: number;
  readonly located: number;
  /** Mean mm of the located darts from the target, a hit counting 0; null without any. */
  readonly distance: number | null;
}
