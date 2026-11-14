import { CheckoutMode } from '../../game/models/checkout-mode';
import { PlayerCount } from '../../game/models/game-filter';
import { GameMode } from '../../game/models/game-mode';
import { GameVariant } from '../../game/models/game-variant';
import { ClockZone, KillerZone, TrainingGoal, TrainingRing } from '../../game/models/variant-options';

/** Narrows the statistics to any of each list's values; an empty list or null leaves them
 * open. `until` is exclusive. */
export interface StatisticsFilter {
  readonly variants: readonly GameVariant[];
  readonly modes: readonly GameMode[];
  readonly checkoutModes: readonly CheckoutMode[];
  readonly killerZones: readonly KillerZone[];
  readonly clockZones: readonly ClockZone[];
  readonly trainingGoals: readonly TrainingGoal[];
  readonly trainingRings: readonly TrainingRing[];
  readonly opponentIds: readonly string[];
  readonly playerCounts: readonly PlayerCount[];
  readonly since: Date | null;
  readonly until: Date | null;
  /** Keeps only this many of the most recent games that count. */
  readonly lastGames: number | null;
}
