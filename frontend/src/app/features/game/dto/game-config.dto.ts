import {GameMode} from "../models/game-mode";
import {CheckoutMode} from "../models/checkout-mode";
import {GameVariant} from "../models/game-variant";
import {PlayerSlotDto} from "./player-slot.dto";
import {ClockOptionsDto} from "./clock-options.dto";
import {CricketOptionsDto} from "./cricket-options.dto";
import {KillerOptionsDto} from "./killer-options.dto";

export interface GameConfigDto {
  readonly players: readonly PlayerSlotDto[];
  /** Required for the points variants, ignored by the others. */
  readonly mode: GameMode;
  readonly variant: GameVariant;
  readonly checkoutMode: CheckoutMode;
  readonly cricket?: CricketOptionsDto;
  readonly killer?: KillerOptionsDto;
  readonly aroundTheClock?: ClockOptionsDto;
  readonly evaluationEnabled: boolean;
  readonly rematchOf?: string;
}
