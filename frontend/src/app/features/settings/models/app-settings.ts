/** Technical settings, persisted locally and shared across features. */
export interface AppSettings {
  readonly manualEntryEnabled: boolean;
  readonly confirmThrowEnabled: boolean;
  readonly debugCalibration: boolean;
  readonly debugDetection: boolean;
  readonly debugClientDetection: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  manualEntryEnabled: true,
  confirmThrowEnabled: true,
  debugCalibration: false,
  debugDetection: false,
  debugClientDetection: false,
};
