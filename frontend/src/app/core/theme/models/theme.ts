import { readStored } from '../../storage/models/browser-storage';

/** Light or dark, or whatever the device itself is set to. */
export type ThemeMode = 'system' | 'light' | 'dark';

export const THEME_MODES: readonly ThemeMode[] = ['system', 'light', 'dark'];

/** Storage key of this device's choice. */
export const THEME_KEY = 'dart-tracking.theme';

/** Class on `<html>` that switches PrimeNG and the app's own styles to dark. */
export const DARK_CLASS = 'app-dark';

export const SYSTEM_DARK_QUERY = '(prefers-color-scheme: dark)';

/** The device's stored choice, `system` without one. */
export function storedThemeMode(): ThemeMode {
  const stored = readStored(THEME_KEY);
  return THEME_MODES.find((mode) => mode === stored) ?? 'system';
}

/** Whether `mode` shows dark, given whether the device prefers dark. */
export function isDark(mode: ThemeMode, systemDark: boolean): boolean {
  return mode === 'dark' || (mode === 'system' && systemDark);
}

/** Set the dark class and the native colour scheme on `<html>`. */
export function applyDark(root: HTMLElement, dark: boolean): void {
  root.classList.toggle(DARK_CLASS, dark);
  root.style.colorScheme = dark ? 'dark' : 'light';
}
