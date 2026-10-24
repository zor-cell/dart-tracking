import { GameStatus } from '../dto/game-summary.dto';
import { GameMode } from './game-mode';
import { GameVariant } from './game-variant';

/** Narrows the game history; a null field leaves it open. `until` is exclusive. */
export interface GameFilter {
  readonly variant: GameVariant | null;
  readonly mode: GameMode | null;
  readonly status: GameStatus | null;
  readonly opponentId: string | null;
  readonly since: Date | null;
  readonly until: Date | null;
}

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
