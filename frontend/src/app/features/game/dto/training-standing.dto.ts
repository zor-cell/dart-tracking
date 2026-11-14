import { TrainingFieldDto } from './training-settings.dto';

export interface TrainingTallyDto extends TrainingFieldDto {
  readonly darts: number;
  readonly hits: number;
}

export interface TrainingPlayerDto {
  /** The field to hit next; null without a target. */
  readonly target: TrainingFieldDto | null;
  /** Hits the target still takes before the next one comes up. */
  readonly left: number;
  readonly darts: number;
  readonly hits: number;
  /** Hits of the last closed visit; null before it. */
  readonly lastVisit: number | null;
  /** Darts and hits per target, in the order the targets first came up. */
  readonly tallies: readonly TrainingTallyDto[];
}

export interface TrainingStandingDto {
  readonly variant: 'training';
  /** One per player, in seat order. */
  readonly players: readonly TrainingPlayerDto[];
}
