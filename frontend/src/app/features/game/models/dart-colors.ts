/**
 * The colour a dart of the current visit is drawn in, by its position in that
 * visit.
 *
 * Shared between the two views of one throw: the outline over the camera
 * picture and the marker on the scoreboard's drawn board. The same dart has to
 * be the same colour on both, since that is what lets someone holding the
 * scoreboard say which of the outlines on the camera phone they mean.
 *
 * Lives with the game rather than with either view because the visit is what it
 * indexes — colour 1 means "first dart of this visit", not "first thing the
 * detector found".
 */
const DART_COLORS = [
  '#648fff', // dart 1 — blue
  '#ffb000', // dart 2 — amber
  '#dc267f', // dart 3 — magenta
] as const;

/** The colour of a shadow dart: located after the visit closed, not counted. */
export const SHADOW_DART_COLOR = '#9aa0a6';

/**
 * The colour for the dart at `index`, held at the last one beyond the third: an
 * over-eager trigger can land more than three detections in one visit, and
 * there are only three colours.
 */
export function dartColor(index: number): string {
  return DART_COLORS[Math.min(index, DART_COLORS.length - 1)];
}
