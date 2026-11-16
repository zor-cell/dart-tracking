import { fieldOutline } from '../../game/models/board-face';
import { parseField } from '../../game/models/field-label';
import { SECTOR_ORDER } from '../../game/models/board-geometry';
import { GAME_SECTIONS, GameVariant, countsPoints, variantLabel } from '../../game/models/game-variant';

/** The games the statistics page shows figures for, one at a time. */
export type StatisticsGame = GameVariant;

/** The games under the kinds of the new game page. */
export const STATISTICS_SECTIONS: readonly {
  kind: string;
  games: readonly { label: string; value: StatisticsGame }[];
}[] = GAME_SECTIONS.map((section) => ({
  kind: section.kind,
  games: section.games.map((value) => ({ label: variantLabel(value), value })),
}));

export const STATISTICS_GAMES = STATISTICS_SECTIONS.flatMap((section) => section.games);

/** What the statistics page shows: one game, or every game together. */
export type StatisticsView = StatisticsGame | 'all';

export const STATISTICS_VIEWS: readonly { label: string; value: StatisticsView }[] = [
  { label: $localize`:@@stats.all:Alle`, value: 'all' },
  ...STATISTICS_GAMES,
];

/** Whether the figures of a game are points and checkouts rather than darts at targets. */
export function showsPoints(game: StatisticsGame): boolean {
  return countsPoints(game);
}

/** A target as it is called out: T19, D16, 16 for any ring of it, 25 and Bull. */
export function targetLabel(target: { readonly value: number; readonly multiplier: number | null }): string {
  if (target.value === 25) {
    return target.multiplier === 2 ? 'Bull' : '25';
  }
  return `${target.multiplier === 2 ? 'D' : target.multiplier === 3 ? 'T' : ''}${target.value}`;
}

/** The label the board models know the target's field by; null for a whole number. */
export function targetField(target: { readonly value: number; readonly multiplier: number | null }): string | null {
  if (target.multiplier === null) {
    return null;
  }
  if (target.value === 25) {
    return target.multiplier === 2 ? '50' : '25';
  }
  return `${target.multiplier === 2 ? 'D' : target.multiplier === 3 ? 'T' : ''}${target.value}`;
}

type TargetRef = { readonly value: number; readonly multiplier: number | null };

/** How the board knows a target: its field's label, `any:16` for every ring of a number. */
export function targetKey(target: TargetRef): string {
  return targetField(target) ?? `any:${target.value}`;
}

/** The outline of the target `key` names, every ring of it for a whole number. */
export function targetOutline(key: string): string | null {
  if (!key.startsWith('any:')) {
    return fieldOutline(key, 0);
  }
  const value = key.slice(4);
  const labels = value === '25' ? ['25', '50'] : [value, `D${value}`, `T${value}`];
  return labels.map((label) => fieldOutline(label, 0) ?? '').join(' ');
}

/** The target among `keys` a dart in the field `label` went for: that field, else its number. */
export function targetAt(label: string, keys: ReadonlySet<string>): string | null {
  const field = parseField(label);
  if (field === null) {
    return null;
  }
  const value = 'index' in field ? SECTOR_ORDER[field.index] : 25;
  return [label, `any:${value}`].find((key) => keys.has(key)) ?? null;
}
