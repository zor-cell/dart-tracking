import { HeatmapCell } from './hit-pattern.dto';
import { TargetTallyDto } from './target-tally.dto';

export interface FieldTallyDto extends TargetTallyDto {
  readonly value: number;
  /** The ring that counts; null takes any ring of the number. */
  readonly multiplier: number | null;
  readonly locatedHits: number;
  /** Darts per field they hit, by called-out label, a miss as 0. */
  readonly fields: Readonly<Record<string, number>>;
  /** Where the located darts landed. */
  readonly cells: readonly HeatmapCell[];
}
