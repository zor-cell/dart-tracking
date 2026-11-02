import { Translation } from 'primeng/api';

/** Intl's week data, which the TypeScript lib does not describe yet. */
interface WeekLocale {
  getWeekInfo?(): { firstDay: number };
}

/** PrimeNG's own labels in `locale`: names and formats from Intl, the rest translated. */
export function primeNgTranslation(locale: string): Translation {
  // 1 January 2023 was a Sunday, the first day of PrimeNG's week.
  const week = Array.from({ length: 7 }, (_, day) => new Date(2023, 0, 1 + day));
  const year = Array.from({ length: 12 }, (_, month) => new Date(2023, month, 1));
  const names = (dates: Date[], options: Intl.DateTimeFormatOptions) => {
    const format = new Intl.DateTimeFormat(locale, options);
    return dates.map((date) => format.format(date).replace(/\.$/, ''));
  };
  const days = names(week, { weekday: 'short' });

  return {
    firstDayOfWeek: firstDayOfWeek(locale),
    dayNames: names(week, { weekday: 'long' }),
    dayNamesShort: days,
    dayNamesMin: days,
    monthNames: names(year, { month: 'long' }),
    monthNamesShort: names(year, { month: 'short' }),
    dateFormat: dateFormat(locale),
    today: $localize`:@@primeng.today:Heute`,
    clear: $localize`:@@primeng.clear:Leeren`,
    weekHeader: $localize`:@@primeng.weekHeader:KW`,
    emptyMessage: $localize`:@@primeng.emptyMessage:Keine Einträge`,
    emptyFilterMessage: $localize`:@@primeng.emptyFilterMessage:Keine Ergebnisse`,
    emptySearchMessage: $localize`:@@primeng.emptySearchMessage:Keine Ergebnisse`,
    searchMessage: $localize`:@@primeng.searchMessage:{0} Ergebnisse`,
    selectionMessage: $localize`:@@primeng.selectionMessage:{0} ausgewählt`,
    emptySelectionMessage: $localize`:@@primeng.emptySelectionMessage:Nichts ausgewählt`,
    accept: $localize`:@@primeng.accept:Ja`,
    reject: $localize`:@@primeng.reject:Nein`,
    choose: $localize`:@@primeng.choose:Auswählen`,
    cancel: $localize`:@@primeng.cancel:Abbrechen`,
  };
}

/** 0 for Sunday as PrimeNG counts, from Intl's 7; Monday where Intl has no week data. */
function firstDayOfWeek(locale: string): number {
  return ((new Intl.Locale(locale) as WeekLocale).getWeekInfo?.().firstDay ?? 1) % 7;
}

/** The locale's numeric date in PrimeNG's pattern letters, e.g. `dd.mm.yy`. */
function dateFormat(locale: string): string {
  const letters: Partial<Record<Intl.DateTimeFormatPartTypes, string>> = {
    day: 'dd',
    month: 'mm',
    year: 'yy',
  };
  return new Intl.DateTimeFormat(locale, { day: '2-digit', month: '2-digit', year: 'numeric' })
    .formatToParts(new Date(2023, 0, 1))
    .map((part) => letters[part.type] ?? part.value)
    .join('');
}
