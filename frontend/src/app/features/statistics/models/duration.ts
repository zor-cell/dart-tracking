import { formatNumber } from '@angular/common';

/** A time span read the way people say it: 31 h, 4,5 h, 13 min. */
export function duration(seconds: number, locale: string): string {
  const hours = seconds / 3600;
  if (hours >= 1) {
    return `${formatNumber(hours, locale, hours < 10 ? '1.0-1' : '1.0-0')} h`;
  }
  return `${formatNumber(seconds / 60, locale, '1.0-0')} min`;
}
