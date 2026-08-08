/**
 * Canonical dartboard geometry, in millimetres from the centre, in the same
 * board plane the server scores in: origin at the bullseye, x right, y **up**,
 * angles counter-clockwise from +x.
 *
 * Mirrors the server's `calibration/domain/board_geometry.py`. It is duplicated
 * rather than fetched because it is a fixed standard, and because it is used
 * here only to draw — the scoring stays server-side.
 */

export const BULLSEYE_RADIUS = 6.35; // the 50
export const BULL_RADIUS = 15.9; // the 25
export const TRIPLE_INNER_RADIUS = 99;
export const TRIPLE_OUTER_RADIUS = 107;
export const DOUBLE_INNER_RADIUS = 162;
export const DOUBLE_OUTER_RADIUS = 170; // outer edge of the scoring area

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

/**
 * Whether the double/triple ring of sector `index` is red rather than green —
 * the colours alternate, and sector 20 is red. Its single beds are the dark
 * ones, so this decides both.
 */
export function isRedSector(index: number): boolean {
  return index % 2 === 0;
}

/**
 * Board millimetres to SVG user units. Only the y axis changes: board y points
 * up, SVG y points down, so the drawing keeps the orientation of the real board.
 */
export function toSvg(x: number, y: number): readonly [number, number] {
  return [x, -y];
}
