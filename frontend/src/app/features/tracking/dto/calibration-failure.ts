/**
 * Why a calibration attempt failed, mirroring the backend's
 * `entity/calibration_failure.py`. Each value names the stage that gave up, so
 * the user can be told what to change.
 */
export type CalibrationFailure =
  | 'invalid_image'
  | 'no_coloured_region'
  | 'ellipse_fit_failed'
  | 'sector_wires_unclear'
  | 'homography_failed';
