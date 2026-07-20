/** Technical settings, persisted locally and shared across features. */
export interface AppSettings {
  readonly manualEntryEnabled: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  manualEntryEnabled: true,
};
