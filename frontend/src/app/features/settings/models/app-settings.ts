/** Technical settings, persisted locally and shared across features. */
export interface AppSettings {
  readonly manualEntryEnabled: boolean;
  readonly debugCalibration: boolean;
  // Server-side: asks the backend to dump the per-stage detection images.
  readonly debugDetection: boolean;
  // Client-side: shows the live frame-diff overlay, numbers and event log in the
  // camera view — what the *trigger* is doing, independent of the backend dump.
  readonly debugClientDetection: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  manualEntryEnabled: true,
  debugCalibration: false,
  debugDetection: false,
  debugClientDetection: false,
};
