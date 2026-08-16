import { CalibrationFailureDto } from './calibration-failure.dto';

/**
 * Server -> room: which camera just calibrated, and whether it worked.
 *
 * The slim counterpart to `CalibrationResultDto`, which only its own camera can
 * use — its overlay is in that camera's pixel grid. This carries the part every
 * device can act on: that a camera is calibrated, or which one is not.
 */
export interface CalibrationStatusDto {
  readonly type: 'calibration_status';
  readonly clientId: string;
  readonly success: boolean;
  readonly failure: CalibrationFailureDto | null;
}
