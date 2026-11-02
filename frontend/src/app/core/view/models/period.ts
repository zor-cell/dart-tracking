import { DayRange, dayRangeBounds } from './day-range';

/** Whether the quick picks count back in days or in games. */
export type PeriodUnit = 'days' | 'games';

/** A quick pick of what a view covers; `custom` opens a date range. */
export type Period =
  | 'days7'
  | 'days30'
  | 'days90'
  | 'days365'
  | 'custom'
  | 'games10'
  | 'games25'
  | 'games50'
  | 'games100'
  | 'all';

export const PERIOD_UNITS: readonly { label: string; value: PeriodUnit }[] = [
  { label: $localize`:@@common.period.time:Zeit`, value: 'days' },
  { label: $localize`:@@common.period.games:Spiele`, value: 'games' },
];

export const PERIODS: Record<PeriodUnit, readonly { label: string; value: Period }[]> = {
  days: [
    { label: $localize`:@@common.period.days7Short:7 T`, value: 'days7' },
    { label: $localize`:@@common.period.days30Short:30 T`, value: 'days30' },
    { label: $localize`:@@common.period.days90Short:90 T`, value: 'days90' },
    { label: $localize`:@@common.period.year:Jahr`, value: 'days365' },
    { label: $localize`:@@common.period.all:Alle`, value: 'all' },
    { label: $localize`:@@common.period.custom:Eigener Zeitraum`, value: 'custom' },
  ],
  games: [
    { label: '10', value: 'games10' },
    { label: '25', value: 'games25' },
    { label: '50', value: 'games50' },
    { label: '100', value: 'games100' },
    { label: $localize`:@@common.period.all:Alle`, value: 'all' },
  ],
};

/** How the active pick reads as a chip; `custom` shows the picked days instead. */
export const PERIOD_CHIP_LABELS: Record<Period, string> = {
  days7: $localize`:@@common.period.days7:Letzte 7 Tage`,
  days30: $localize`:@@common.period.days30:Letzte 30 Tage`,
  days90: $localize`:@@common.period.days90:Letzte 90 Tage`,
  days365: $localize`:@@common.period.lastYear:Letztes Jahr`,
  custom: $localize`:@@common.period.custom:Eigener Zeitraum`,
  games10: $localize`:@@common.period.games10:Letzte 10 Spiele`,
  games25: $localize`:@@common.period.games25:Letzte 25 Spiele`,
  games50: $localize`:@@common.period.games50:Letzte 50 Spiele`,
  games100: $localize`:@@common.period.games100:Letzte 100 Spiele`,
  all: $localize`:@@common.period.everything:Gesamter Verlauf`,
};

/** The pick a unit starts on. */
export const DEFAULT_PERIODS: Record<PeriodUnit, Period> = {
  days: 'days30',
  games: 'games10',
};

/** Days a quick pick reaches back, today included. */
const PERIOD_DAYS: Partial<Record<Period, number>> = {
  days7: 7,
  days30: 30,
  days90: 90,
  days365: 365,
};

/** Most recent games a quick pick keeps. */
const PERIOD_GAMES: Partial<Record<Period, number>> = {
  games10: 10,
  games25: 25,
  games50: 50,
  games100: 100,
};

/** Midnight of the first day a quick pick covers; null when it has no start. */
export function periodStart(period: Period, today: Date): Date | null {
  const days = PERIOD_DAYS[period];
  return days === undefined
    ? null
    : new Date(today.getFullYear(), today.getMonth(), today.getDate() - days + 1);
}

/** How many of the latest games a quick pick keeps; null when it counts days. */
export function periodGames(period: Period): number | null {
  return PERIOD_GAMES[period] ?? null;
}

/** The days a pick covers as query bounds, `until` exclusive; `range` is read for `custom`. */
export function periodBounds(
  period: Period,
  range: DayRange,
  today: Date,
): { since: Date | null; until: Date | null } {
  return period === 'custom'
    ? dayRangeBounds(range)
    : { since: periodStart(period, today), until: null };
}
