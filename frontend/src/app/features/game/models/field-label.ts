import { SECTOR_ORDER } from './board-geometry';

/** A board field as named by a called-out label: 20, D20, T20, 25, 50. */
export type Field =
  | { readonly ring: 'single' | 'double' | 'triple'; readonly index: number }
  | { readonly ring: 'bull' | 'bullseye' };

/** The field `label` names, its sector as an index into SECTOR_ORDER; null for a miss. */
export function parseField(label: string): Field | null {
  if (label === '50') {
    return { ring: 'bullseye' };
  }
  if (label === '25') {
    return { ring: 'bull' };
  }
  const match = /^([DT]?)(\d+)$/.exec(label);
  const index = match ? SECTOR_ORDER.indexOf(Number(match[2])) : -1;
  if (match === null || index < 0) {
    return null;
  }
  return { ring: match[1] === 'D' ? 'double' : match[1] === 'T' ? 'triple' : 'single', index };
}

/** Points of a called-out field: 20, D20, T20, 25, 50, 0. */
export function labelPoints(label: string): number {
  const multiplier = label.startsWith('T') ? 3 : label.startsWith('D') ? 2 : 1;
  return multiplier * Number(label.replace(/^[DT]/, ''));
}

/** How a field is written for people: T20, D16, 20, Bull, Double Bull, Daneben. */
export function fieldName(label: string): string {
  if (label === '0') {
    return 'Daneben';
  }
  return label === '50' ? 'Double Bull' : label === '25' ? 'Bull' : label;
}
