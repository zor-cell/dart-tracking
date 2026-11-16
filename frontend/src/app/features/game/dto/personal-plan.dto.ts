import { PersonalFocus, PersonalLength } from '../models/variant-options';
import { FieldRecordDto } from './field-record.dto';
import { PlanBlockDto } from './plan-block.dto';

export interface PlannedFieldDto extends FieldRecordDto {
  /** The ring's darts and hits over every field: the player's average there. */
  readonly ringDarts: number;
  readonly ringHits: number;
  /** Whether enough darts tell the rate; a thin field is in the plan to learn it. */
  readonly telling: boolean;
  /** Where most missing darts landed, as called out. */
  readonly missedTo: string | null;
}

export interface LengthPlanDto {
  readonly length: PersonalLength;
  readonly blocks: readonly PlanBlockDto[];
}

export interface FocusPlanDto {
  readonly focus: PersonalFocus;
  /** The planned fields' records, in plan order. */
  readonly fields: readonly PlannedFieldDto[];
  readonly lengths: readonly LengthPlanDto[];
}

/** The plan a training of each focus and length would start on now, with what they are drawn from. */
export interface PersonalPlanDto {
  readonly games: number;
  readonly darts: number;
  readonly foci: readonly FocusPlanDto[];
}
