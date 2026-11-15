/**
 * The colour a dart of the current visit is drawn in, by its position in the
 * visit, the same on the camera outline and the scoreboard's board.
 */
const DART_COLORS = [
  '#648fff', // dart 1 — blue
  '#ffb000', // dart 2 — amber
  '#dc267f', // dart 3 — magenta
] as const;

/** The colour of a shadow dart: located after the visit closed, not counted. */
export const SHADOW_DART_COLOR = '#9aa0a6';

/** The colour of a located dart that was booked as another field by hand. */
export const CORRECTED_DART_COLOR = 'rgba(154, 160, 166, 0.55)';

/**
 * The colour for the dart at `index`, held at the last one beyond the third: an
 * over-eager trigger can land more than three detections in one visit, and
 * there are only three colours.
 */
export function dartColor(index: number): string {
  return DART_COLORS[Math.min(index, DART_COLORS.length - 1)];
}
