import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { redirectToRememberedLanguage } from './app/core/i18n/models/language';
import { SYSTEM_DARK_QUERY, applyDark, isDark, storedThemeMode } from './app/core/theme/models/theme';

if (!redirectToRememberedLanguage()) {
  applyDark(document.documentElement, isDark(storedThemeMode(), matchMedia(SYSTEM_DARK_QUERY).matches));
  // Safari on iOS shows :active on a tap only while some touch listener exists.
  document.addEventListener('touchstart', () => undefined, { passive: true });
  bootstrapApplication(AppComponent, appConfig)
    .catch((err) => console.error(err));
}
