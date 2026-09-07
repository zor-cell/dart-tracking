import {GameMode} from "../models/game-mode";
import {CheckoutMode} from "../models/checkout-mode";
import {PlayerSlotDto} from "./player-slot.dto";

export interface GameConfigDto {
  readonly players: readonly PlayerSlotDto[];
  readonly mode: GameMode;
  readonly checkoutMode: CheckoutMode;
  readonly evaluationEnabled: boolean;
}
