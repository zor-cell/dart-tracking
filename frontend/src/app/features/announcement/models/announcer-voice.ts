import { Language } from '../../../core/i18n/models/language';

/** Each language offers two announcer voices; the first is the default. */
export type AnnouncerVoice = 'first' | 'second';

/** What each voice is called, per language: the speaker the Piper model was trained on. */
export const VOICE_NAMES: Record<Language, Record<AnnouncerVoice, string>> = {
  de: { first: 'Thorsten', second: 'Pavoque' },
  en: { first: 'Alan', second: 'Jenny' },
};
