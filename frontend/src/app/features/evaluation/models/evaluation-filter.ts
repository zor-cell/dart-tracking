import { GameMode } from '../../game/models/game-mode';

/** Narrows the evaluated games to any of each list's values; an empty list or null leaves
 * them open. `until` is exclusive. */
export interface EvaluationFilter {
  /** Tracker versions every event of a game has to come from. */
  readonly versions: readonly number[];
  readonly modes: readonly GameMode[];
  /** True for test runs only, false for ordinary games only. */
  readonly testRun: boolean | null;
  readonly since: Date | null;
  readonly until: Date | null;
}

/** Whether a game was marked as a test run. */
export type RunKind = 'test' | 'normal';

export const RUN_KIND_LABELS: Record<RunKind, string> = {
  test: 'Testlauf',
  normal: 'Normales Spiel',
};
