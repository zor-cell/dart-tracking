import { CheckoutMode } from '../models/checkout-mode';
import { GameMode } from '../models/game-mode';
import { GameVariant } from '../models/game-variant';
import { ClockOptionsDto } from './clock-options.dto';
import { CricketOptionsDto } from './cricket-options.dto';
import { KillerOptionsDto } from './killer-options.dto';

export interface QuickStartSeatDto {
  /** The identity to seat, or null to seat a guest by `name`. */
  readonly playerId: string | null;
  readonly name: string;
}

/** The setup the account plays most, with the players of its latest game. */
export interface QuickStartDto {
  readonly variant: GameVariant;
  readonly mode: GameMode | null;
  readonly checkoutMode: CheckoutMode | null;
  readonly cricket: CricketOptionsDto | null;
  readonly killer: KillerOptionsDto | null;
  readonly aroundTheClock: ClockOptionsDto | null;
  readonly players: readonly QuickStartSeatDto[];
}
