/** Client -> server: a single still frame to calibrate the board against. */
export interface CalibrationFrameDto {
  readonly type: 'calibration_frame';
  readonly image: string; // base64-encoded JPEG
  readonly debug?: boolean;
}
