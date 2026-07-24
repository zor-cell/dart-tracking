import { CalibrationFailureDto } from './calibration-failure.dto';

/**
 * Server -> client: outcome of a calibration attempt.
 *
 * `overlay` is the recognised board projected back onto the camera picture, as
 * polylines of [x, y] points normalized to 0..1 of the image size, so it can be
 * drawn at whatever size the video happens to be displayed at.
 *
 * `failure` names which stage gave up, and is only set when `success` is false.
 */
export interface CalibrationResultDto {
  readonly type: 'calibration_result';
  readonly success: boolean;
  readonly homography: number[][] | null;
  readonly overlay: number[][][] | null;
  readonly failure: CalibrationFailureDto | null;
}
