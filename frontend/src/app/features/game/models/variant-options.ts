// The settings of Cricket, Killer, Around the Clock and Elimination; values match the backend enums.

export type CricketScoring = 'standard' | 'cut_throat' | 'no_score';
export type KillerZone = 'double' | 'triple' | 'any';
export type ClockZone = 'any' | 'double' | 'triple';
export type EliminationKill = 'any' | 'double';

export const CRICKET_SCORINGS: readonly { label: string; value: CricketScoring }[] = [
  { label: 'Standard', value: 'standard' },
  { label: 'Cut-Throat', value: 'cut_throat' },
  { label: $localize`:@@game.variant.noScoreShort:Ohne`, value: 'no_score' },
];

/** How a game's scoring reads on its own, outside the form that sits under "Punkte". */
export function scoringLabel(scoring: CricketScoring): string {
  return scoring === 'no_score'
    ? $localize`:@@game.variant.noScore:Ohne Punkte`
    : optionLabel(CRICKET_SCORINGS, scoring);
}

export const KILLER_ZONES: readonly { label: string; value: KillerZone }[] = [
  { label: 'Single', value: 'any' },
  { label: 'Double', value: 'double' },
  { label: 'Triple', value: 'triple' },
];

export const CLOCK_ZONES: readonly { label: string; value: ClockZone }[] = [
  { label: 'Single', value: 'any' },
  { label: 'Double', value: 'double' },
  { label: 'Triple', value: 'triple' },
];

export const ELIMINATION_KILLS: readonly { label: string; value: EliminationKill }[] = [
  { label: 'Single', value: 'any' },
  { label: 'Double', value: 'double' },
];

export const KILLER_LIVES: readonly number[] = [3, 5];

/** A field as it is called out: the zone's prefix before the number, the bull as 25 or 50. */
export function zoneLabel(value: number, zone: KillerZone | ClockZone): string {
  if (value === 25) {
    return zone === 'any' ? '25' : '50';
  }
  return `${zone === 'double' ? 'D' : zone === 'triple' ? 'T' : ''}${value}`;
}

export function optionLabel<T>(options: readonly { label: string; value: T }[], value: T): string {
  return options.find((option) => option.value === value)?.label ?? '';
}
