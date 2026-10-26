import { CheckoutMode } from '../../game/models/checkout-mode';
import { GameMode } from '../../game/models/game-mode';

/** Narrows the statistics to some games; a null field leaves them open. `until` is exclusive. */
export interface StatisticsFilter {
  readonly mode: GameMode | null;
  readonly checkoutMode: CheckoutMode | null;
  readonly opponentId: string | null;
  /** Bounds on the number of players, both inclusive. */
  readonly minPlayers: number | null;
  readonly maxPlayers: number | null;
  readonly since: Date | null;
  readonly until: Date | null;
}
