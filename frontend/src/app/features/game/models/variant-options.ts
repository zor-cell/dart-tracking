// The settings of Cricket, Killer and Around the Clock; values match the backend enums.

export type CricketScoring = 'standard' | 'cut_throat' | 'no_score';
export type KillerZone = 'double' | 'triple' | 'any';
export type ClockZone = 'any' | 'double' | 'triple';

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
  { label: 'Double', value: 'double' },
  { label: 'Triple', value: 'triple' },
  { label: $localize`:@@game.variant.anyRing:Ganze Zahl`, value: 'any' },
];

export const CLOCK_ZONES: readonly { label: string; value: ClockZone }[] = [
  { label: $localize`:@@game.variant.anyRing:Ganze Zahl`, value: 'any' },
  { label: 'Double', value: 'double' },
  { label: 'Triple', value: 'triple' },
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
