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
 *
 * Everything here is in this camera's image space, and only that. Where the
 * dart landed on the board comes as board millimetres on `DartDto.position`
 * instead, which is camera-independent and so drawable by every device in the
 * room (docs/feature/done/multi-device.md §4a). The two look alike as pairs of
 * numbers and may never be mixed, so they do not share a message.
 */
export interface DetectionResultDto {
  readonly type: 'detection_result';
  readonly success: boolean;
  readonly segment: string | null; // called-out form, e.g. 'T20', 'BULL', 'MISS'
  readonly points: number | null;
  readonly overlay: number[][][] | null; // dart axis + tip, normalized to 0..1
  readonly failure: DetectionFailureDto | null;
}
