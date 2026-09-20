/**
 * Canonical dartboard geometry in millimetres: origin at the bullseye, x right,
 * y **up**, angles counter-clockwise from +x. Used only to draw; scoring stays
 * server-side in `calibration/domain/board_geometry.py`, which this mirrors.
 */

export const BULLSEYE_RADIUS = 6.35; // the 50
export const BULL_RADIUS = 15.9; // the 25
// Double and treble share one width, measured apex to apex.
export const RING_WIDTH = 9.2;
export const TRIPLE_OUTER_RADIUS = 107.4;
export const TRIPLE_INNER_RADIUS = TRIPLE_OUTER_RADIUS - RING_WIDTH;
export const DOUBLE_OUTER_RADIUS = 170; // outer edge of the scoring area
export const DOUBLE_INNER_RADIUS = DOUBLE_OUTER_RADIUS - RING_WIDTH;

export const SECTOR_COUNT = 20;
export const SECTOR_ANGLE = (2 * Math.PI) / SECTOR_COUNT; // 18 degrees

/** Sector values clockwise starting at 20, which by convention hangs on top. */
export const SECTOR_ORDER: readonly number[] = [
  20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5,
];

/** Sector 20 is centred straight up. */
const FIRST_SECTOR_CENTRE_ANGLE = Math.PI / 2;

/** Angle (radians) of the centre of the sector at `index` in SECTOR_ORDER. */
export function sectorCentreAngle(index: number): number {
  return FIRST_SECTOR_CENTRE_ANGLE - index * SECTOR_ANGLE;
}

/** Whether sector `index` is a red/dark one rather than green/light — the
 * colours alternate, and sector 20 is red. */
export function isRedSector(index: number): boolean {
  return index % 2 === 0;
}

/** Board millimetres to SVG user units: board y points up, SVG y down. */
export function toSvg(x: number, y: number): readonly [number, number] {
  return [x, -y];
}
