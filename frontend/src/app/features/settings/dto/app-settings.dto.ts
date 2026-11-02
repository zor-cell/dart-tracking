import { Language } from '../../../core/i18n/models/language';

/**
 * The whole set of switches, both ways: the answer to a read and the body of a
 * write. Sent complete rather than as a patch, so a switch never has an
 * undefined state on the wire.
 */
export interface AppSettingsDto {
  readonly advanceOnPull: boolean;
  readonly evaluationEnabled: boolean;
  readonly language: Language | null; // null until the account picks one
  readonly preferredDoubles: readonly number[]; // by sector, 25 for bull, in order
}
