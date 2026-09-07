/**
 * The whole set of switches, both ways: the answer to a read and the body of a
 * write. Sent complete rather than as a patch, so a switch never has an
 * undefined state on the wire.
 */
export interface AppSettingsDto {
  readonly manualEntryEnabled: boolean;
  readonly confirmThrowEnabled: boolean;
  readonly evaluationEnabled: boolean;
  readonly debugCalibration: boolean;
  readonly debugDetection: boolean;
  readonly debugClientDetection: boolean;
}
