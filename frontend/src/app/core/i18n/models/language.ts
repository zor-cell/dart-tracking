import { environment } from '../../../../environments/environment';

/** The languages the app is built in; each is served under its own path, e.g. `/en/`. */
export type Language = 'de' | 'en';

/** Each language named in itself, as a switch offers it. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  de: 'Deutsch',
  en: 'English',
};

/** The flag each language is shown with, under `public/flags/`. */
export const LANGUAGE_FLAGS: Record<Language, string> = {
  de: 'flags/de.svg',
  en: 'flags/gb.svg',
};

/** The cookie nginx reads to route a path without language to `/de/` or `/en/`. */
export const LANGUAGE_COOKIE = 'lang';

/** The language a build's `LOCALE_ID` belongs to. */
export function languageOf(locale: string): Language {
  return locale.startsWith('en') ? 'en' : 'de';
}

/** The language the cookie in `cookies` (as `document.cookie` lists them) names, if any. */
export function rememberedLanguage(cookies: string): string | undefined {
  return cookies
    .split('; ')
    .find((entry) => entry.startsWith(`${LANGUAGE_COOKIE}=`))
    ?.slice(LANGUAGE_COOKIE.length + 1);
}

/**
 * On the dev server with both languages, go where the cookie points, as nginx
 * does. True when the page is being left.
 */
export function redirectToRememberedLanguage(): boolean {
  const remembered = rememberedLanguage(document.cookie);
  if (
    !environment.languageSwitch ||
    !remembered ||
    remembered === languageOf($localize.locale ?? 'de')
  ) {
    return false;
  }
  location.replace(`/${remembered}${location.pathname}${location.search}${location.hash}`);
  return true;
}
