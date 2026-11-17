import { TrainingFieldDto } from './training-settings.dto';

export interface FieldRecordDto extends TrainingFieldDto {
  readonly darts: number;
  readonly hits: number;
  readonly located: number;
  /** Mean mm of the located darts from the field, 0 for a hit; null without one. */
  readonly distance: number | null;
}
