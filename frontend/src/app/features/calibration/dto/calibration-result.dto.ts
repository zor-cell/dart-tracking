import { CalibrationFailureDto } from './calibration-failure.dto';

/**
 * Server -> client: outcome of a calibration attempt. `overlay` is the board as
 * polylines of [x, y] points normalized to 0..1 of the image size; `failure` names
 * the stage that gave up when `success` is false.
 */
export interface CalibrationResultDto {
  readonly type: 'calibration_result';
  readonly success: boolean;
  readonly overlay: number[][][] | null;
  readonly failure: CalibrationFailureDto | null;
}
