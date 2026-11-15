/** Server -> camera: take a fresh frame and calibrate from it. */
export interface CalibrationRequestedDto {
  readonly type: 'calibration_requested';
}
