/** How far the game's board calibration is; mirrors the server's `CalibrationState`. */
export type CalibrationState = 'no_camera' | 'uncalibrated' | 'calibrating' | 'calibrated' | 'failed';

/** Server -> room: how far the game's board calibration is. */
export interface CalibrationStateDto {
  readonly type: 'calibration_state';
  readonly state: CalibrationState;
}
