import { PersonalFocus, PersonalLength, TrainingMinutes } from '../models/variant-options';

export interface PersonalSettingsDto {
  readonly variant: 'personal';
  readonly focus: PersonalFocus;
  /** Darts in the plan. */
  readonly length: PersonalLength;
  /** Whether a single is hit by its double and triple too. */
  readonly anyRing: boolean;
  /** Minutes the plan runs from its first dart; null plays it by darts. */
  readonly minutes: TrainingMinutes | null;
}
