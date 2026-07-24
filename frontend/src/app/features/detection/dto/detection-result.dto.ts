import { DetectionFailureDto } from './detection-failure.dto';

/**
 * Server -> client: outcome of locating a dart in a throw frame.
 *
 * Mirrors `CalibrationResultMessage`: on success it carries where the dart
 * landed and what it scored, plus an `overlay` (the dart as polylines normalized
 * to 0..1 of the image size) so it can be drawn over the preview like the board
 * outline; on failure `failure` names the stage that gave up.
 *
 * The authoritative score arrives separately as `game_state` — this is the
 * per-throw feedback, not the source of truth for the tally.
 */
export interface DetectionResultDto {
  readonly type: 'detection_result';
  readonly success: boolean;
  readonly segment: string | null; // called-out form, e.g. 'T20', 'BULL', 'MISS'
  readonly points: number | null;
  readonly value: number | null; // sector value, 25 for the bull, 0 for a miss
  readonly multiplier: number | null; // 0 miss, 1 single, 2 double, 3 triple
  readonly tipBoard: number[] | null; // [x, y] in board millimetres
  readonly overlay: number[][][] | null; // dart axis + tip, normalized to 0..1
  readonly failure: DetectionFailureDto | null;
}
