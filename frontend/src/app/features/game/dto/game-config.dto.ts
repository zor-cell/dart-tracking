import {GameMode} from "../models/game-mode";
import {CheckoutMode} from "../models/checkout-mode";
import {GameVariant} from "../models/game-variant";
import {PlayerSlotDto} from "./player-slot.dto";

export interface GameConfigDto {
  readonly players: readonly PlayerSlotDto[];
  readonly mode: GameMode;
  readonly variant: GameVariant;
  readonly checkoutMode: CheckoutMode;
  readonly evaluationEnabled: boolean;
  readonly rematchOf?: string;
}
