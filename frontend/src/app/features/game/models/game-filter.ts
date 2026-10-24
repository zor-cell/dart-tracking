import { GameStatus } from '../dto/game-summary.dto';
import { GameMode } from './game-mode';
import { GameVariant } from './game-variant';

/** Narrows the game history; a null field leaves it open. `until` is exclusive. */
export interface GameFilter {
  readonly variant: GameVariant | null;
  readonly mode: GameMode | null;
  readonly status: GameStatus | null;
  readonly opponentId: string | null;
  /** Bounds on the number of players, both inclusive. */
  readonly minPlayers: number | null;
  readonly maxPlayers: number | null;
  readonly since: Date | null;
  readonly until: Date | null;
}

/** How many players the game list can be narrowed to. */
export type PlayerCount = 'solo' | 'duel' | 'group';

interface PlayerCountRange {
  readonly label: string;
  readonly min: number;
  readonly max: number | null;
}

export const PLAYER_COUNTS: Record<PlayerCount, PlayerCountRange> = {
  solo: { label: 'Allein', min: 1, max: 1 },
  duel: { label: 'Zu zweit', min: 2, max: 2 },
  group: { label: 'Ab drei', min: 3, max: null },
};

export const GAME_STATUS_LABELS: Record<GameStatus, string> = {
  active: 'läuft',
  finished: 'beendet',
  abandoned: 'abgebrochen',
  discarded: 'verworfen',
};

export type GameStatusSeverity = 'success' | 'secondary' | 'warn' | 'danger';

/** The p-tag colour each status is shown in. */
export const GAME_STATUS_SEVERITIES: Record<GameStatus, GameStatusSeverity> = {
  active: 'success',
  finished: 'secondary',
  abandoned: 'warn',
  discarded: 'danger',
};
