/** One stretch of a progress bar: how full it is in percent, its share of the bar, and its name. */
export interface ProgressSegment {
  readonly value: number;
  readonly weight: number;
  readonly label: string;
}
