import { GameSettingsDto } from '../dto/game-settings.dto';
import { CHECKOUT_HINTS, CLOCK_ZONE_HINTS, KILL_HINTS, KILLER_ZONE_HINTS, SCORING_HINTS, SettingHint } from './setting-hints';
import { variantLabel } from './game-variant';
import { TRAINING_GOALS, TRAINING_RINGS, fieldLabel, optionLabel } from './variant-options';

/** A setting that differs from its default, shown as a short mark beside a setup's name. */
export interface SetupBadge {
  /** Letters on the mark, if any; drawn before the icon. */
  readonly label: string | null;
  /** A PrimeIcons class, if any. */
  readonly icon: string | null;
  /** What the mark stands for. */
  readonly title: string;
  /** What that means, if it needs saying. */
  readonly hint: string | null;
}

const CATCH_UP = $localize`:@@game.new.catchUp:Mit Nachziehen`;
const CATCH_UP_HINT = $localize`:@@game.new.catchUpHint:Ist jemand fertig, werfen die übrigen die Runde noch zu Ende. Sind dann mehrere fertig, wiederholen nur sie die Runde, jeder ab seinem Stand davor.`;
const PLAY_ON = $localize`:@@game.new.playOn:Plätze ausspielen`;
const PLAY_ON_HINT = $localize`:@@game.new.playOnHint:Nach dem Sieger wird weitergespielt, bis alle Plätze vergeben sind.`;
const SKIP = $localize`:@@game.new.clockSkip:Double und Triple springen weiter`;

/** A setup's name: the game, and the points it plays to where it has them. */
export function setupName(settings: GameSettingsDto): string {
  const name = variantLabel(settings.variant);
  return 'mode' in settings ? `${name} ${settings.mode}` : name;
}

/** The setup's settings that differ from their defaults, in the order the form shows them. */
export function setupBadges(settings: GameSettingsDto): SetupBadge[] {
  const badges: SetupBadge[] = [];
  if ('checkoutMode' in settings && settings.checkoutMode === 'single_out') {
    badges.push(lettered('SO', CHECKOUT_HINTS[0]));
  }
  switch (settings.variant) {
    case 'elimination':
      if (settings.kill === 'double') {
        badges.push(lettered('DK', { ...KILL_HINTS[1], label: 'Double Kill' }));
      }
      break;
    case 'cricket':
      if (settings.scoring === 'cut_throat') {
        badges.push(lettered('CT', SCORING_HINTS[1]));
      }
      if (settings.scoring === 'no_score') {
        badges.push(iconed('pi-ban', $localize`:@@game.variant.noScore:Ohne Punkte`, SCORING_HINTS[2].text));
      }
      break;
    case 'killer':
      if (settings.lives !== 3) {
        const lives = $localize`:@@game.detail.lives:${settings.lives}:count: Leben`;
        badges.push({ label: `${settings.lives}`, icon: 'pi-heart', title: lives, hint: null });
      }
      if (settings.zone !== 'double') {
        const hint = KILLER_ZONE_HINTS[settings.zone === 'any' ? 0 : 2];
        badges.push(lettered(hint.label[0], hint));
      }
      break;
    case 'around_the_clock':
      if (settings.zone !== 'any') {
        const hint = CLOCK_ZONE_HINTS[settings.zone === 'double' ? 1 : 2];
        badges.push(lettered(hint.label[0], hint));
      }
      if (settings.skip) {
        badges.push(iconed('pi-forward', SKIP, null));
      }
      break;
    case 'training':
      if (settings.goal === 'random') {
        const ring = optionLabel(TRAINING_RINGS, settings.ring);
        badges.push(iconed('pi-sync', `${optionLabel(TRAINING_GOALS, 'random')}, ${ring}`, null));
      }
      if (settings.goal === 'fields') {
        const fields = settings.fields.map(fieldLabel).join(' ');
        badges.push({ label: fields, icon: null, title: optionLabel(TRAINING_GOALS, 'fields'), hint: null });
      }
      break;
  }
  if ('catchUp' in settings && settings.catchUp) {
    badges.push(iconed('pi-replay', CATCH_UP, CATCH_UP_HINT));
  }
  if ('playOn' in settings && settings.playOn) {
    badges.push(iconed('pi-sort-numeric-down', PLAY_ON, PLAY_ON_HINT));
  }
  return badges;
}

function lettered(label: string, hint: SettingHint): SetupBadge {
  return { label, icon: null, title: hint.label, hint: hint.text };
}

function iconed(icon: string, title: string, hint: string | null): SetupBadge {
  return { label: null, icon, title, hint };
}
