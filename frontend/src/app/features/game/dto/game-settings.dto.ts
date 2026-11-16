import { ClockSettingsDto } from './clock-settings.dto';
import { CricketSettingsDto } from './cricket-settings.dto';
import { EliminationSettingsDto } from './elimination-settings.dto';
import { KillerSettingsDto } from './killer-settings.dto';
import { PersonalSettingsDto } from './personal-settings.dto';
import { TrainingSettingsDto } from './training-settings.dto';
import { X01SettingsDto } from './x01-settings.dto';

/** The settings of a game: one shape per variant, told apart by `variant`. */
export type GameSettingsDto =
  | X01SettingsDto
  | EliminationSettingsDto
  | CricketSettingsDto
  | KillerSettingsDto
  | ClockSettingsDto
  | TrainingSettingsDto
  | PersonalSettingsDto;
