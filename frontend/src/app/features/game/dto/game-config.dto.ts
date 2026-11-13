import {GameMode} from "../models/game-mode";
import {CheckoutMode} from "../models/checkout-mode";
import {GameVariant} from "../models/game-variant";
import {PlayerSlotDto} from "./player-slot.dto";
import {ClockOptionsDto} from "./clock-options.dto";
import {CricketOptionsDto} from "./cricket-options.dto";
import {KillerOptionsDto} from "./killer-options.dto";
import {EliminationOptionsDto} from "./elimination-options.dto";

export interface GameConfigDto {
  readonly players: readonly PlayerSlotDto[];
  /** Required for the points variants, ignored by the others. */
  readonly mode: GameMode | null;
  readonly variant: GameVariant;
  readonly checkoutMode: CheckoutMode | null;
  readonly cricket?: CricketOptionsDto | null;
  readonly killer?: KillerOptionsDto | null;
  readonly aroundTheClock?: ClockOptionsDto | null;
  readonly elimination?: EliminationOptionsDto | null;
  /** How a race ends; ignored outside the race variants. */
  readonly catchUp?: boolean;
  readonly playOn?: boolean;
  readonly evaluationEnabled: boolean;
  readonly rematchOf?: string;
}
