import { PlayerIdentityDto } from '../../player/dto/player-identity.dto';
import { GameMode } from './game-mode';
import { CheckoutMode } from './checkout-mode';
import { GameVariant } from './game-variant';
import { TrainingFieldDto } from '../dto/training-settings.dto';
import {
  ClockZone,
  CricketScoring,
  EliminationKill,
  KillerZone,
  PersonalEnd,
  PersonalFocus,
  PersonalLength,
  TrainingEnd,
  TrainingGoal,
  TrainingMinutes,
  TrainingRing,
} from './variant-options';

/** What a seat holds: a known identity, or the name typed for a guest. */
export type Seat = PlayerIdentityDto | string;

/** A new game's setup as far as it got: the picked game, its settings and seats. */
export interface GameDraft {
  /** The account it was set up under, null when signed out. */
  readonly account: string | null;
  /** The game of the second step, null while still on the list. */
  readonly chosen: GameVariant | null;
  readonly settings: {
    readonly mode: GameMode;
    readonly variant: GameVariant;
    readonly checkoutMode: CheckoutMode;
    readonly cricketScoring: CricketScoring;
    readonly killerLives: number;
    readonly killerZone: KillerZone;
    readonly clockZone: ClockZone;
    readonly clockSkip: boolean;
    readonly eliminationKill: EliminationKill;
    readonly trainingGoal: TrainingGoal;
    readonly trainingRing: TrainingRing;
    readonly trainingFields: readonly TrainingFieldDto[];
    readonly trainingRepeats: number;
    readonly trainingShuffle: boolean;
    readonly trainingAnyRing: boolean;
    readonly trainingEnd: TrainingEnd;
    readonly trainingDarts: PersonalLength;
    readonly trainingMinutes: TrainingMinutes;
    readonly personalFocus: PersonalFocus;
    readonly personalLength: PersonalLength;
    readonly personalAnyRing: boolean;
    readonly personalEnd: PersonalEnd;
    readonly personalMinutes: TrainingMinutes;
    readonly catchUp: boolean;
    readonly playOn: boolean;
  };
  readonly seats: readonly Seat[];
}
