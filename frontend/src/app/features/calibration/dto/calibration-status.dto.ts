/**
 * Server -> requester: whether a camera's calibration attempt worked.
 *
 * The slim counterpart to `CalibrationResultDto`, which only its own camera can
 * use — its overlay is in that camera's pixel grid.
 */
export interface CalibrationStatusDto {
  readonly type: 'calibration_status';
  readonly success: boolean;
}
