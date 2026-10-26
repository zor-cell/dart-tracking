/** A quick pick of the days the statistics cover; `custom` opens a date range. */
export type StatisticsPeriod = 'days7' | 'days30' | 'days90' | 'year' | 'all' | 'custom';

export const STATISTICS_PERIODS: readonly { label: string; value: StatisticsPeriod }[] = [
  { label: '7 T', value: 'days7' },
  { label: '30 T', value: 'days30' },
  { label: '90 T', value: 'days90' },
  { label: 'Jahr', value: 'year' },
  { label: 'Alle', value: 'all' },
  { label: 'Eigener Zeitraum', value: 'custom' },
];

export const DEFAULT_STATISTICS_PERIOD: StatisticsPeriod = 'days30';

/** Days a quick pick reaches back, today included. */
const PERIOD_DAYS: Partial<Record<StatisticsPeriod, number>> = {
  days7: 7,
  days30: 30,
  days90: 90,
  year: 365,
};

/** Midnight of the first day a quick pick covers; null when it has no start. */
export function periodStart(period: StatisticsPeriod, today: Date): Date | null {
  const days = PERIOD_DAYS[period];
  return days === undefined
    ? null
    : new Date(today.getFullYear(), today.getMonth(), today.getDate() - days + 1);
}
