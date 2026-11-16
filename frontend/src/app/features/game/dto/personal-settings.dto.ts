import { PersonalFocus, PersonalLength } from '../models/variant-options';

export interface PersonalSettingsDto {
  readonly variant: 'personal';
  readonly focus: PersonalFocus;
  /** Darts in the plan. */
  readonly length: PersonalLength;
  /** Whether a single is hit by its double and triple too. */
  readonly anyRing: boolean;
}
