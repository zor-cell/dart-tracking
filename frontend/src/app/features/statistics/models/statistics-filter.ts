import { CheckoutMode } from '../../game/models/checkout-mode';
import { PlayerCount } from '../../game/models/game-filter';
import { GameMode } from '../../game/models/game-mode';
import { GameVariant } from '../../game/models/game-variant';

/** Narrows the statistics to any of each list's values; an empty list or null leaves them
 * open. `until` is exclusive. */
export interface StatisticsFilter {
  readonly variants: readonly GameVariant[];
  readonly modes: readonly GameMode[];
  readonly checkoutModes: readonly CheckoutMode[];
  readonly opponentIds: readonly string[];
  readonly playerCounts: readonly PlayerCount[];
  readonly since: Date | null;
  readonly until: Date | null;
  /** Keeps only this many of the most recent games that count. */
  readonly lastGames: number | null;
}
