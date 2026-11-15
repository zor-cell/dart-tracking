import { DetectionFailureDto } from './detection-failure.dto';

/**
 * Server -> client: outcome of locating a dart in a throw frame, in this camera's
 * image space: the dart, its score and an `overlay` normalized to 0..1, or the
 * `failure` stage. The booked score arrives as `game_state`.
 */
export interface DetectionResultDto {
  readonly type: 'detection_result';
  readonly success: boolean;
  readonly segment: string | null; // called-out form, e.g. 'T20', 'BULL', 'MISS'
  readonly points: number | null;
  readonly overlay: number[][][] | null; // dart axis + tip, normalized to 0..1
  readonly failure: DetectionFailureDto | null;
}
