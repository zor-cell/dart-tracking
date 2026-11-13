import { CHECKOUT_MODES } from './checkout-mode';
import { CLOCK_ZONES, CRICKET_SCORINGS, ELIMINATION_KILLS, KILLER_ZONES, optionLabel } from './variant-options';

/** One option of a game setting, explained in the setting's info popover. */
export interface SettingHint {
  readonly label: string;
  readonly text: string;
}

export const CHECKOUT_HINTS: readonly SettingHint[] = [
  {
    label: optionLabel(CHECKOUT_MODES, 'single_out'),
    text: $localize`:@@game.hint.singleOut:Jeder Dart darf das Spiel beenden.`,
  },
  {
    label: optionLabel(CHECKOUT_MODES, 'double_out'),
    text: $localize`:@@game.hint.doubleOut:Der letzte Dart muss ein Double oder das Bull sein. Bleibt 1 Punkt übrig oder fehlt am Ende das Double, ist es ein Bust.`,
  },
];

export const KILL_HINTS: readonly SettingHint[] = [
  {
    label: optionLabel(ELIMINATION_KILLS, 'any'),
    text: $localize`:@@game.hint.killAny:Jeder Dart, der genau auf dem Stand eines anderen landet, schickt ihn auf null zurück.`,
  },
  {
    label: optionLabel(ELIMINATION_KILLS, 'double'),
    text: $localize`:@@game.hint.killDouble:Nur ein Double oder das Bull schickt zurück.`,
  },
];

export const SCORING_HINTS: readonly SettingHint[] = [
  {
    label: optionLabel(CRICKET_SCORINGS, 'standard'),
    text: $localize`:@@game.hint.standard:Die Punkte bekommt, wer wirft. Es gewinnt, wer alles zu hat und mindestens so viele Punkte wie jeder Gegner.`,
  },
  {
    label: optionLabel(CRICKET_SCORINGS, 'cut_throat'),
    text: $localize`:@@game.hint.cutThroat:Die Punkte bekommen die Gegner, die die Zahl noch offen haben. Es gewinnt, wer alles zu hat und die wenigsten Punkte.`,
  },
  {
    label: optionLabel(CRICKET_SCORINGS, 'no_score'),
    text: $localize`:@@game.hint.noScore:Es gibt keine Punkte. Es gewinnt, wer zuerst alles zu hat.`,
  },
];

export const KILLER_ZONE_HINTS: readonly SettingHint[] = [
  {
    label: optionLabel(KILLER_ZONES, 'any'),
    text: $localize`:@@game.hint.killerAny:Jeder Ring zählt: ein Double nimmt 2 Leben, ein Triple 3.`,
  },
  {
    label: optionLabel(KILLER_ZONES, 'double'),
    text: $localize`:@@game.hint.killerDouble:Nur das Double der Zahl zählt, fürs Killer-Werden wie für Leben.`,
  },
  {
    label: optionLabel(KILLER_ZONES, 'triple'),
    text: $localize`:@@game.hint.killerTriple:Nur das Triple der Zahl zählt, fürs Killer-Werden wie für Leben.`,
  },
];

export const CLOCK_ZONE_HINTS: readonly SettingHint[] = [
  {
    label: optionLabel(CLOCK_ZONES, 'any'),
    text: $localize`:@@game.hint.clockAny:Jeder Ring der Zahl zählt, am Ende 25 und Bull.`,
  },
  {
    label: optionLabel(CLOCK_ZONES, 'double'),
    text: $localize`:@@game.hint.clockDouble:Nur das Double zählt, am Ende nur das Bull.`,
  },
  {
    label: optionLabel(CLOCK_ZONES, 'triple'),
    text: $localize`:@@game.hint.clockTriple:Nur das Triple zählt, am Ende nur das Bull.`,
  },
];
