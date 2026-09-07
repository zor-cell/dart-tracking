import { AppSettingsDto } from '../dto/app-settings.dto';

/** What a session runs on until the server says otherwise, and what an
 * anonymous one runs on for good. Mirrors the server's `AppSettings` defaults. */
export const DEFAULT_SETTINGS: AppSettingsDto = {
  manualEntryEnabled: true,
  confirmThrowEnabled: true,
  evaluationEnabled: false,
  debugCalibration: false,
  debugDetection: false,
  debugClientDetection: false,
};
