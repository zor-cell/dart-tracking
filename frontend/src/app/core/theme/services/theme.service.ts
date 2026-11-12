import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { writeStored } from '../../storage/models/browser-storage';
import {
  SYSTEM_DARK_QUERY,
  THEME_KEY,
  ThemeMode,
  applyDark,
  isDark,
  storedThemeMode,
} from '../models/theme';

/** This device's light or dark mode, following the system's while set to `system`. */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);

  private readonly _mode = signal<ThemeMode>(storedThemeMode());
  private readonly systemDark = signal(false);
  readonly mode = this._mode.asReadonly();
  readonly dark = computed(() => isDark(this._mode(), this.systemDark()));

  constructor() {
    const query = this.document.defaultView?.matchMedia(SYSTEM_DARK_QUERY);
    if (query) {
      this.systemDark.set(query.matches);
      const follow = (event: MediaQueryListEvent) => this.systemDark.set(event.matches);
      query.addEventListener('change', follow);
      inject(DestroyRef).onDestroy(() => query.removeEventListener('change', follow));
    }

    effect(() => {
      const root = this.document.documentElement;
      applyDark(root, this.dark());
      const background = getComputedStyle(root).getPropertyValue('--p-content-background').trim();
      if (background) {
        this.document.querySelector('meta[name="theme-color"]')?.setAttribute('content', background);
      }
    });
  }

  setMode(mode: ThemeMode): void {
    this._mode.set(mode);
    writeStored(THEME_KEY, mode === 'system' ? null : mode);
  }
}
