import { FieldRecordDto } from './field-record.dto';
import { PlanBlockDto } from './plan-block.dto';
import { TrainingFieldDto } from './training-settings.dto';

export interface PersonalPlayerDto {
  /** The block under way; the number of blocks once the plan is through. */
  readonly block: number;
  /** The field to hit next; null once the plan is through. */
  readonly target: TrainingFieldDto | null;
  /** Darts the block under way still takes. */
  readonly left: number;
  readonly darts: number;
  readonly hits: number;
  /** Hits of the last closed visit; null before it. */
  readonly lastVisit: number | null;
  /** Darts and hits per block, in plan order. */
  readonly blocks: readonly { readonly darts: number; readonly hits: number }[];
  /** Today's darts and hits per planned field. */
  readonly fields: readonly FieldRecordDto[];
}

export interface PersonalStandingDto {
  readonly variant: 'personal';
  readonly blocks: readonly PlanBlockDto[];
  /** Each planned field's record before the training. */
  readonly baselines: readonly FieldRecordDto[];
  /** One per player, in seat order. */
  readonly players: readonly PersonalPlayerDto[];
  /** Seconds of a timed plan left when the state was sent; null by darts or before the first dart. */
  readonly secondsLeft: number | null;
}
