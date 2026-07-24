/** Technical settings, persisted locally and shared across features. */
export interface AppSettings {
  readonly manualEntryEnabled: boolean;
  readonly debugCalibration: boolean;
  readonly debugDetection: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  manualEntryEnabled: true,
  debugCalibration: false,
  debugDetection: false,
};
