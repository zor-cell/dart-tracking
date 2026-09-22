/** Server -> room: whether the game has a calibrated scoring camera, and whether
 * that camera's latest attempt failed. */
export interface CalibrationStateDto {
  readonly type: 'calibration_state';
  readonly calibrated: boolean;
  readonly failed: boolean;
}
