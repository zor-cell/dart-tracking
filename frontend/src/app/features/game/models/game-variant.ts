// Which direction the score runs: x01 counts down from the mode to zero,
// elimination counts up to it and resets whoever is on the score just hit.
// The string values match the backend GameVariant enum sent over the wire.
export type GameVariant = 'x01' | 'elimination';

export const GAME_VARIANTS: readonly { label: string; value: GameVariant }[] = [
  { label: 'X01', value: 'x01' },
  { label: 'Elimination', value: 'elimination' },
];
