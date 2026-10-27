import { MissDirection } from '../dto/double-statistics.dto';

export const MISS_DIRECTION_LABELS: Readonly<Record<MissDirection, string>> = {
  short: 'zu kurz',
  long: 'zu weit',
  left: 'links',
  right: 'rechts',
};

/** Each direction's share of all misses counted, 0 to 1; null without any. */
export function missShares(
  counts: Readonly<Record<MissDirection, number>>,
): Record<MissDirection, number> | null {
  const total = counts.short + counts.long + counts.left + counts.right;
  if (total === 0) {
    return null;
  }
  return {
    short: counts.short / total,
    long: counts.long / total,
    left: counts.left / total,
    right: counts.right / total,
  };
}
