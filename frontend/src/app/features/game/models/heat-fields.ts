import { HeatField } from '../components/heat-board/heat-board.component';
import { dartCount } from './dart-count';
import { fieldName } from './field-label';

/** Label of a dart that hit no field. */
export const MISS = '0';

/** The highest count on a board field, at least 1, the dark end of the scale; misses stay out. */
export function mostOnBoard(counts: ReadonlyMap<string, number>): number {
  return Math.max(1, ...[...counts].filter(([label]) => label !== MISS).map(([, n]) => n));
}

/** Each board field with its count's share of `most`; misses stay out. */
export function heatFields(counts: ReadonlyMap<string, number>, most: number): HeatField[] {
  return [...counts]
    .filter(([label]) => label !== MISS)
    .map(([label, count]) => ({
      label,
      share: count / most,
      ariaLabel: `${fieldName(label)}: ${dartCount(count)}`,
    }));
}
