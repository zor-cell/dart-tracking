import { formatDate } from '@angular/common';

/** A range from a range date picker: its first and last day, either still unpicked. */
export type DayRange = readonly (Date | null)[] | null;

/** The range as query bounds, `until` exclusive; one day picked covers that day. */
export function dayRangeBounds(range: DayRange): { since: Date | null; until: Date | null } {
  const [start, end] = range ?? [];
  return start ? { since: start, until: nextDay(end ?? start) } : { since: null, until: null };
}

/** "01.10.26 – 07.10.26", or the one day; null while nothing is picked. */
export function dayRangeLabel(range: DayRange, locale: string): string | null {
  const [start, end] = range ?? [];
  if (!start) {
    return null;
  }
  const day = (date: Date) => formatDate(date, 'dd.MM.yy', locale);
  return end && end.getTime() !== start.getTime() ? `${day(start)} – ${day(end)}` : day(start);
}

function nextDay(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1);
}
