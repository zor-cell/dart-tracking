import { CheckoutMode } from '../models/checkout-mode';
import { GameMode } from '../models/game-mode';

export interface X01SettingsDto {
  readonly variant: 'x01';
  readonly mode: GameMode;
  readonly checkoutMode: CheckoutMode;
  /** How the race ends once someone has finished. */
  readonly catchUp: boolean;
  readonly playOn: boolean;
}
