import { GameStatus } from '../dto/game-summary.dto';
import { CheckoutMode } from './checkout-mode';
import { GameMode } from './game-mode';
import { GameVariant } from './game-variant';

/** Narrows the game history to any of each list's values; an empty list or null leaves it
 * open. `until` is exclusive. */
export interface GameFilter {
  /** Part of a player's name. */
  readonly query: string | null;
  readonly variants: readonly GameVariant[];
  readonly modes: readonly GameMode[];
  readonly checkoutModes: readonly CheckoutMode[];
  readonly statuses: readonly GameStatus[];
  readonly opponentIds: readonly string[];
  readonly playerCounts: readonly PlayerCount[];
  readonly since: Date | null;
  readonly until: Date | null;
  /** Points one of the account's own visits reached, busts aside. */
  readonly minVisit: number | null;
}

/** The visit scores the game list can be narrowed to, as the statistics count them. */
export const VISIT_BANDS = [180, 140, 100, 60] as const;

export type VisitBand = (typeof VISIT_BANDS)[number];

/** How a band reads: 180 alone, the others as a floor. */
export function visitBandLabel(band: VisitBand): string {
  return band === 180 ? '180' : `${band}+`;
}

/** How many players the game list can be narrowed to. */
export type PlayerCount = 'solo' | 'duel' | 'group';

export const PLAYER_COUNT_LABELS: Record<PlayerCount, string> = {
  solo: $localize`:@@game.filter.solo:Allein`,
  duel: $localize`:@@game.filter.duel:Zu zweit`,
  group: $localize`:@@game.filter.group:Ab drei`,
};

export const GAME_STATUS_LABELS: Record<GameStatus, string> = {
  active: $localize`:@@game.status.active:läuft`,
  finished: $localize`:@@game.status.finished:beendet`,
  abandoned: $localize`:@@game.status.abandoned:abgebrochen`,
  discarded: $localize`:@@game.status.discarded:ausgeblendet`,
};

export type GameStatusSeverity = 'success' | 'secondary' | 'warn' | 'danger';

/** The p-tag colour each status is shown in. */
export const GAME_STATUS_SEVERITIES: Record<GameStatus, GameStatusSeverity> = {
  active: 'success',
  finished: 'secondary',
  abandoned: 'warn',
  discarded: 'danger',
};

/** Whether a game can be taken up again: it is neither won nor hidden. */
export function isResumable(status: GameStatus): boolean {
  return status === 'active' || status === 'abandoned';
}
