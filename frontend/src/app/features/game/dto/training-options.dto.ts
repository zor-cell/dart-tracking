import { TrainingGoal, TrainingRing } from '../models/variant-options';

/** A board field: 1 to 20 in any ring, 25 as single (25) or double (50). */
export interface TrainingFieldDto {
  readonly value: number;
  readonly multiplier: number;
}

export interface TrainingOptionsDto {
  readonly goal: TrainingGoal;
  /** Which fields a random target is drawn from. */
  readonly ring: TrainingRing;
  /** The own fields; each stays the target until it was hit often enough. */
  readonly fields: readonly TrainingFieldDto[];
  /** Hits a target takes before the next one comes up. */
  readonly repeats: number;
  /** Whether the own fields come up at random rather than in order. */
  readonly shuffle: boolean;
}
