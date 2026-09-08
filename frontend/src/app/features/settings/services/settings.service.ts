import { HttpClient } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SILENT_ERROR_CONTEXT } from '../../../core/interceptors';
import { AuthService } from '../../auth/services/auth.service';
import { AppSettingsDto } from '../dto/app-settings.dto';
import { DEFAULT_SETTINGS } from '../models/app-settings';

/**
 * How this account wants the app to behave. Kept on the server rather than in
 * the browser, so the choices follow the account onto the second phone that
 * joins the same game.
 *
 * Without an account there is nowhere to keep an answer, so the session runs on
 * the defaults and never sees the settings page at all (its route is guarded).
 */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly url = `${environment.httpApiUrl}/settings`;

  private readonly _settings = signal<AppSettingsDto>(DEFAULT_SETTINGS);
  private readonly _loading = signal(true);
  readonly settings = this._settings.asReadonly();
  /** True while the server's answer is still outstanding — until then the
   * signals below hold defaults, not this account's choices. */
  readonly loading = this._loading.asReadonly();

  readonly manualEntryEnabled = computed(() => this._settings().manualEntryEnabled);
  readonly confirmThrowEnabled = computed(() => this._settings().confirmThrowEnabled);
  readonly evaluationEnabled = computed(() => this._settings().evaluationEnabled);
  readonly debugCalibration = computed(() => this._settings().debugCalibration);
  readonly debugDetection = computed(() => this._settings().debugDetection);
  readonly debugClientDetection = computed(() => this._settings().debugClientDetection);

  constructor() {
    // Left over from when these lived in the browser; the server owns them now.
    localStorage.removeItem('dart-tracking.settings');

    // Kicks off the session restore. The effect below is what reacts to it, and
    // to a later sign-in or sign-out.
    void this.auth.ready;

    effect(() => {
      if (this.auth.user()) {
        this._loading.set(true);
        void this.reload();
      } else {
        this._settings.set(DEFAULT_SETTINGS);
        this._loading.set(false);
      }
    });
  }

  setManualEntryEnabled(enabled: boolean): void {
    this.patch({ manualEntryEnabled: enabled });
  }

  setConfirmThrowEnabled(enabled: boolean): void {
    this.patch({ confirmThrowEnabled: enabled });
  }

  setEvaluationEnabled(enabled: boolean): void {
    this.patch({ evaluationEnabled: enabled });
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

  /** Apply a change locally so the switch answers at once, then let the server
   * confirm it. Anonymous cannot reach the page, and has nothing to write to. */
  private patch(changes: Partial<AppSettingsDto>): void {
    if (!this.auth.isAuthenticated()) {
      return;
    }
    const next = { ...this._settings(), ...changes };
    this._settings.set(next);
    void this.save(next);
  }

  private async save(settings: AppSettingsDto): Promise<void> {
    try {
      this._settings.set(await firstValueFrom(this.http.put<AppSettingsDto>(this.url, settings)));
    } catch {
      // The change did not stick; show what the server actually holds rather
      // than leaving the switch lying.
      await this.reload();
    }
  }

  private async reload(): Promise<void> {
    try {
      this._settings.set(
        await firstValueFrom(
          this.http.get<AppSettingsDto>(this.url, { context: SILENT_ERROR_CONTEXT }),
        ),
      );
    } catch {
      this._settings.set(DEFAULT_SETTINGS);
    } finally {
      this._loading.set(false);
    }
  }
}
