/** Server -> room: whether the game has a calibrated camera that scores it. */
export interface CalibrationStateDto {
  readonly type: 'calibration_state';
  readonly calibrated: boolean;
}
