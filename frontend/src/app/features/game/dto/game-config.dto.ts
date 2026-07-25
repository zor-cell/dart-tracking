import {GameMode} from "../models/game-mode";
import {CheckoutMode} from "../models/checkout-mode";

export interface GameConfigDto {
  readonly playerNames: readonly string[];
  readonly mode: GameMode;
  readonly checkoutMode: CheckoutMode;
}