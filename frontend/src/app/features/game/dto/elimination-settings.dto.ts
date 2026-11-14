import { CheckoutMode } from '../models/checkout-mode';
import { GameMode } from '../models/game-mode';
import { EliminationKill } from '../models/variant-options';

export interface EliminationSettingsDto {
  readonly variant: 'elimination';
  readonly mode: GameMode;
  readonly checkoutMode: CheckoutMode;
  /** Which darts send an opponent back to zero. */
  readonly kill: EliminationKill;
  readonly catchUp: boolean;
  readonly playOn: boolean;
}
