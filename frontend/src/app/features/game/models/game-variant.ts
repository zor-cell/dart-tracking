// Which game is played. x01 counts down from the mode to zero, elimination counts up to it;
// the string values match the backend GameVariant enum sent over the wire.
export type GameVariant = 'x01' | 'elimination' | 'cricket' | 'killer' | 'around_the_clock';

export const GAME_VARIANTS: readonly { label: string; value: GameVariant }[] = [
  { label: 'X01', value: 'x01' },
  { label: 'Elimination', value: 'elimination' },
  { label: 'Cricket', value: 'cricket' },
  { label: 'Killer', value: 'killer' },
  { label: 'Around the Clock', value: 'around_the_clock' },
];

/** The variants that run on a points total and have a mode and a checkout. */
export const POINTS_VARIANTS = GAME_VARIANTS.filter((option) => countsPoints(option.value));

export function countsPoints(variant: GameVariant): boolean {
  return variant === 'x01' || variant === 'elimination';
}

export function variantLabel(variant: GameVariant): string {
  return GAME_VARIANTS.find((option) => option.value === variant)?.label ?? '';
}
