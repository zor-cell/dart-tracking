/**
 * Why a calibration attempt failed, mirroring the backend's
 * `domain/calibration_failure.py`. Each value names the stage that gave up, so
 * the user can be told what to change.
 */
export type CalibrationFailureDto =
  | 'invalid_image'
  | 'ellipse_fit_failed'
  | 'sector_wires_unclear'
  | 'homography_failed';
