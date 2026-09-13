/**
 * Why locating a dart failed, mirroring the backend's
 * `domain/detection_failure.py`. Each value names the stage that gave up, so
 * the user can be told what to change.
 */
export type DetectionFailureDto =
  | 'invalid_image'
  | 'not_calibrated'
  | 'alignment_failed'
  | 'no_change'
  | 'implausible_shape'
  | 'darts_removed';
