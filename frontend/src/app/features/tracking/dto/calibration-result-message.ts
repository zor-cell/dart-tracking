/**
 * Server -> client: outcome of a calibration attempt.
 *
 * `homography` is a stub for now (identity matrix on success) — real board
 * detection (Hough/contour -> homography) lands once test footage from
 * zeitplan.md Phase 1 is available.
 */
export interface CalibrationResultMessage {
  readonly type: 'calibration_result';
  readonly success: boolean;
  readonly homography: number[][] | null;
}
