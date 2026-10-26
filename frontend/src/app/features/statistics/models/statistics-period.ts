/** Whether the quick picks count back in days or in games. */
export type StatisticsUnit = 'days' | 'games';

/** A quick pick of what the statistics cover; `custom` opens a date range. */
export type StatisticsPeriod =
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

export const STATISTICS_UNITS: readonly { label: string; value: StatisticsUnit }[] = [
  { label: 'Zeit', value: 'days' },
  { label: 'Spiele', value: 'games' },
];

export const STATISTICS_PERIODS: Record<
  StatisticsUnit,
  readonly { label: string; value: StatisticsPeriod }[]
> = {
  days: [
    { label: '7 T', value: 'days7' },
    { label: '30 T', value: 'days30' },
    { label: '90 T', value: 'days90' },
    { label: 'Jahr', value: 'days365' },
    { label: 'Alle', value: 'all' },
    { label: 'Eigener Zeitraum', value: 'custom' },
  ],
  games: [
    { label: '10', value: 'games10' },
    { label: '25', value: 'games25' },
    { label: '50', value: 'games50' },
    { label: '100', value: 'games100' },
    { label: 'Alle', value: 'all' },
  ],
};

/** How the active pick reads as a chip; `custom` shows the picked days instead. */
export const PERIOD_CHIP_LABELS: Record<StatisticsPeriod, string> = {
  days7: 'Letzte 7 Tage',
  days30: 'Letzte 30 Tage',
  days90: 'Letzte 90 Tage',
  days365: 'Letztes Jahr',
  custom: 'Eigener Zeitraum',
  games10: 'Letzte 10 Spiele',
  games25: 'Letzte 25 Spiele',
  games50: 'Letzte 50 Spiele',
  games100: 'Letzte 100 Spiele',
  all: 'Gesamter Verlauf',
};

/** The pick a unit starts on. */
export const DEFAULT_PERIODS: Record<StatisticsUnit, StatisticsPeriod> = {
  days: 'days30',
  games: 'games10',
};

/** Days a quick pick reaches back, today included. */
const PERIOD_DAYS: Partial<Record<StatisticsPeriod, number>> = {
  days7: 7,
  days30: 30,
  days90: 90,
  days365: 365,
};

/** Most recent games a quick pick keeps. */
const PERIOD_GAMES: Partial<Record<StatisticsPeriod, number>> = {
  games10: 10,
  games25: 25,
  games50: 50,
  games100: 100,
};

/** Midnight of the first day a quick pick covers; null when it has no start. */
export function periodStart(period: StatisticsPeriod, today: Date): Date | null {
  const days = PERIOD_DAYS[period];
  return days === undefined
    ? null
    : new Date(today.getFullYear(), today.getMonth(), today.getDate() - days + 1);
}

/** How many of the latest games a quick pick keeps; null when it counts days. */
export function periodGames(period: StatisticsPeriod): number | null {
  return PERIOD_GAMES[period] ?? null;
}
