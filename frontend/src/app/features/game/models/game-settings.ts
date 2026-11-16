import { ClockSettingsDto } from '../dto/clock-settings.dto';
import { ClockStandingDto } from '../dto/clock-standing.dto';
import { CricketSettingsDto } from '../dto/cricket-settings.dto';
import { CricketStandingDto } from '../dto/cricket-standing.dto';
import { EliminationSettingsDto } from '../dto/elimination-settings.dto';
import { GameSettingsDto } from '../dto/game-settings.dto';
import { GameStandingDto } from '../dto/game-standing.dto';
import { KillerSettingsDto } from '../dto/killer-settings.dto';
import { KillerStandingDto } from '../dto/killer-standing.dto';
import { PersonalSettingsDto } from '../dto/personal-settings.dto';
import { PersonalStandingDto } from '../dto/personal-standing.dto';
import { TrainingSettingsDto } from '../dto/training-settings.dto';
import { TrainingStandingDto } from '../dto/training-standing.dto';
import { X01SettingsDto } from '../dto/x01-settings.dto';
import { GameMode } from './game-mode';
import { variantLabel } from './game-variant';

/** The settings of a variant with the standing that belongs to them. */
export type VariantPlay =
  | { readonly variant: 'x01'; readonly settings: X01SettingsDto; readonly standing: null }
  | { readonly variant: 'elimination'; readonly settings: EliminationSettingsDto; readonly standing: null }
  | { readonly variant: 'cricket'; readonly settings: CricketSettingsDto; readonly standing: CricketStandingDto }
  | { readonly variant: 'killer'; readonly settings: KillerSettingsDto; readonly standing: KillerStandingDto }
  | {
      readonly variant: 'around_the_clock';
      readonly settings: ClockSettingsDto;
      readonly standing: ClockStandingDto;
    }
  | { readonly variant: 'training'; readonly settings: TrainingSettingsDto; readonly standing: TrainingStandingDto }
  | { readonly variant: 'personal'; readonly settings: PersonalSettingsDto; readonly standing: PersonalStandingDto };

/** A game state read by its variant, so one check narrows settings and standing together. */
export function playOf(game: {
  readonly settings: GameSettingsDto;
  readonly standing: GameStandingDto | null;
}): VariantPlay {
  return { variant: game.settings.variant, settings: game.settings, standing: game.standing } as VariantPlay;
}

/** The starting score of a points variant; null for the others. */
export function modeOf(settings: GameSettingsDto): GameMode | null {
  return 'mode' in settings ? settings.mode : null;
}

/** How a race ends; both false outside the race variants. */
export function finishOf(settings: GameSettingsDto): { readonly catchUp: boolean; readonly playOn: boolean } {
  return 'catchUp' in settings
    ? { catchUp: settings.catchUp, playOn: settings.playOn }
    : { catchUp: false, playOn: false };
}

/** A game named as its detail page heads it: "X01 501", "Cricket". */
export function gameTitle(settings: GameSettingsDto): string {
  return `${variantLabel(settings.variant)} ${modeOf(settings) ?? ''}`.trim();
}
