import { GameMode } from '../../game/models/game-mode';

/** Narrows the evaluated games; an empty list or null leaves them open. `until` is
 * exclusive. */
export interface EvaluationFilter {
  /** Tracker versions every event of a game has to lie between, both inclusive. */
  readonly versionFrom: number | null;
  readonly versionTo: number | null;
  readonly modes: readonly GameMode[];
  /** True for test runs only, false for ordinary games only. */
  readonly testRun: boolean | null;
  readonly since: Date | null;
  readonly until: Date | null;
  /** Bounds on the scoring camera's tilt to the board in degrees, both inclusive. */
  readonly tiltFrom: number | null;
  readonly tiltTo: number | null;
}

/** A range of tracker versions, either end open. */
export type VersionRange = readonly [number | null, number | null];

/** A range of camera tilts in degrees. */
export type TiltRange = readonly [number, number];

/** Every tilt the slider offers; a range spanning it narrows nothing. */
export const TILT_LIMITS: TiltRange = [0, 90];

/** Whether a game was marked as a test run. */
export type RunKind = 'test' | 'normal';

export const RUN_KIND_LABELS: Record<RunKind, string> = {
  test: $localize`:@@eval.testRun:Testlauf`,
  normal: $localize`:@@eval.normalGame:Normales Spiel`,
};
