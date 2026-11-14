import { ClockStandingDto } from './clock-standing.dto';
import { CricketStandingDto } from './cricket-standing.dto';
import { KillerStandingDto } from './killer-standing.dto';
import { TrainingStandingDto } from './training-standing.dto';

/** Where everyone stands in a variant with own rules, told apart by `variant`. */
export type GameStandingDto =
  | CricketStandingDto
  | KillerStandingDto
  | ClockStandingDto
  | TrainingStandingDto;
