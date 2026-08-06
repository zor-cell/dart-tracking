import { Injectable, computed, signal } from '@angular/core';
import { AppSettings, DEFAULT_SETTINGS } from '../models/app-settings';

const STORAGE_KEY = 'dart-tracking.settings';

/**
 * Local, client-only settings. Unlike the game state these are not
 * server-authoritative — they configure how this device behaves, so they live in
 * localStorage and survive a refresh.
 */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly _settings = signal<AppSettings>(this.load());
  readonly settings = this._settings.asReadonly();

  readonly manualEntryEnabled = computed(() => this._settings().manualEntryEnabled);
  readonly confirmThrowEnabled = computed(() => this._settings().confirmThrowEnabled);
  readonly debugCalibration = computed(() => this._settings().debugCalibration);
  readonly debugDetection = computed(() => this._settings().debugDetection);
  readonly debugClientDetection = computed(() => this._settings().debugClientDetection);

  setManualEntryEnabled(enabled: boolean): void {
    this.patch({ manualEntryEnabled: enabled });
  }

  setConfirmThrowEnabled(enabled: boolean): void {
    this.patch({ confirmThrowEnabled: enabled });
  }

  setDebugCalibration(enabled: boolean): void {
    this.patch({ debugCalibration: enabled });
  }

  setDebugDetection(enabled: boolean): void {
    this.patch({ debugDetection: enabled });
  }

  setDebugClientDetection(enabled: boolean): void {
    this.patch({ debugClientDetection: enabled });
  }

  private patch(changes: Partial<AppSettings>): void {
    const next = { ...this._settings(), ...changes };
    this._settings.set(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  private load(): AppSettings {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_SETTINGS;
    }
    try {
      // Spread over the defaults so settings added in a later version are
      // present even when an older payload is still stored.
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    } catch {
      return DEFAULT_SETTINGS;
    }
  }
}
