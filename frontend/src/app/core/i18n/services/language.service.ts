import { DOCUMENT } from '@angular/common';
import { Injectable, LOCALE_ID, inject } from '@angular/core';
import { Router } from '@angular/router';
import { LANGUAGE_COOKIE, Language, languageOf, rememberedLanguage } from '../models/language';

/** Which language this app was built in, and the way over to the other one. */
@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);

  readonly current = languageOf(inject(LOCALE_ID));

  /** Remember `language` for this browser and reopen the current page in it. */
  switchTo(language: Language): void {
    this.document.cookie = `${LANGUAGE_COOKIE}=${language}; path=/; max-age=31536000; samesite=lax`;
    if (language !== this.current) {
      // A path without language: nginx, or main.ts on the dev server with both, follows the cookie.
      this.document.location.assign(this.router.url);
    }
  }

  /** Follow an account's stored choice once, so a server with one language never loops. */
  adopt(language: Language | null): void {
    if (language && language !== rememberedLanguage(this.document.cookie)) {
      this.switchTo(language);
    }
  }
}
