import { TrainingFieldDto } from './training-settings.dto';

export interface FieldRecordDto extends TrainingFieldDto {
  readonly darts: number;
  readonly hits: number;
}
