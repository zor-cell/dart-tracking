// The settings of Cricket, Killer, Around the Clock and Elimination; values match the backend enums.

export type CricketScoring = 'standard' | 'cut_throat' | 'no_score';
export type KillerZone = 'double' | 'triple' | 'any';
export type ClockZone = 'any' | 'double' | 'triple';
export type EliminationKill = 'any' | 'double';
export type TrainingGoal = 'free' | 'random' | 'fields';
export type TrainingRing = 'single' | 'double' | 'triple' | 'mixed';
export type PersonalFocus = 'singles' | 'doubles' | 'triples' | 'all';
export type PersonalLength = 45 | 90 | 150;

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

export const TRAINING_GOALS: readonly { label: string; value: TrainingGoal }[] = [
  { label: $localize`:@@game.training.free:Frei`, value: 'free' },
  { label: $localize`:@@game.training.random:Zufall`, value: 'random' },
  { label: $localize`:@@game.training.fields:Eigene Felder`, value: 'fields' },
];

export const TRAINING_RINGS: readonly { label: string; value: TrainingRing }[] = [
  { label: 'Single', value: 'single' },
  { label: 'Double', value: 'double' },
  { label: 'Triple', value: 'triple' },
  { label: $localize`:@@game.training.mixed:Gemischt`, value: 'mixed' },
];

export const PERSONAL_FOCI: readonly { label: string; value: PersonalFocus }[] = [
  { label: 'Single', value: 'singles' },
  { label: 'Double', value: 'doubles' },
  { label: 'Triple', value: 'triples' },
  { label: $localize`:@@game.training.mixed:Gemischt`, value: 'all' },
];

/** Whether a personal training's focus takes singles, where double and triple may count too. */
export function personalHasSingles(focus: PersonalFocus): boolean {
  return focus === 'singles' || focus === 'all';
}

export const PERSONAL_LENGTHS: readonly { label: string; value: PersonalLength }[] = [
  { label: $localize`:@@game.personal.short:Kurz`, value: 45 },
  { label: $localize`:@@game.personal.medium:Mittel`, value: 90 },
  { label: $localize`:@@game.personal.long:Lang`, value: 150 },
];

/** Hits a training target may take before the next one comes up. */
export const TRAINING_REPEATS: readonly number[] = [1, 2, 3, 5];

/** A field as it is called out: T19, D16, 19, 25, 50. */
export function fieldLabel(field: { readonly value: number; readonly multiplier: number }): string {
  if (field.value === 25) {
    return field.multiplier === 2 ? '50' : '25';
  }
  return `${field.multiplier === 2 ? 'D' : field.multiplier === 3 ? 'T' : ''}${field.value}`;
}

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
