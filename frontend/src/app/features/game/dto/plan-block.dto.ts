import { TrainingFieldDto } from './training-settings.dto';

/** One block of a personal training: one field, or every planned field in turn. */
export interface PlanBlockDto {
  readonly fields: readonly TrainingFieldDto[];
  readonly darts: number;
}
