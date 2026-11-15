/** Client -> server: have the game's cameras calibrate again. */
export interface RequestCalibrationDto {
  readonly type: 'request_calibration';
}
