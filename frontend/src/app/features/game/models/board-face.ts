/**
 * The drawn dartboard: every ring band as an SVG path, plus the sector numbers.
 * Built once — the board is a fixed standard and never changes.
 */

import {
  BULL_RADIUS,
  DOUBLE_INNER_RADIUS,
  DOUBLE_OUTER_RADIUS,
  SECTOR_ANGLE,
  SECTOR_COUNT,
  SECTOR_ORDER,
  TRIPLE_INNER_RADIUS,
  TRIPLE_OUTER_RADIUS,
  isRedSector,
  sectorCentreAngle,
  toSvg,
} from './board-geometry';

/** One drawn ring band of one sector; `tone` picks the colour from the stylesheet. */
export interface BoardSegment {
  readonly d: string;
  readonly tone: 'dark' | 'light' | 'red' | 'green';
}

/** A sector value drawn outside the double ring. */
export interface SectorNumber {
  readonly x: number;
  readonly y: number;
  readonly value: number;
}

/** Where the sector values sit, far enough out to clear the double ring. */
const NUMBER_RADIUS = 186;

/** The drawn board disc; a tip beyond it has no place on the face. */
export const BOARD_BACKING_RADIUS = 200;

/** Where a dart that landed off the board is marked, in the margin around it. */
export const OFF_BOARD_MARKER_RADIUS = 202;

/** Half the drawn area's edge length: the board plus the off-board margin. */
const VIEW_EXTENT = 216;

export const BOARD_VIEW_BOX = `${-VIEW_EXTENT} ${-VIEW_EXTENT} ${VIEW_EXTENT * 2} ${VIEW_EXTENT * 2}`;

/**
 * Builds one ring band of one sector as an SVG path: along the inner arc,
 * outwards, back along the outer arc, closed. The angles grow counter-clockwise
 * in board space, which the flipped y turns into counter-clockwise on screen —
 * hence the differing sweep flags of the two arcs.
 */
function band(index: number, innerRadius: number, outerRadius: number): string {
  const centre = sectorCentreAngle(index);
  const start = centre - SECTOR_ANGLE / 2;
  const end = centre + SECTOR_ANGLE / 2;

  const point = (angle: number, radius: number): string => {
    const [x, y] = toSvg(radius * Math.cos(angle), radius * Math.sin(angle));
    return `${x.toFixed(2)} ${y.toFixed(2)}`;
  };

  return (
    `M ${point(start, innerRadius)}` +
    ` A ${innerRadius} ${innerRadius} 0 0 0 ${point(end, innerRadius)}` +
    ` L ${point(end, outerRadius)}` +
    ` A ${outerRadius} ${outerRadius} 0 0 1 ${point(start, outerRadius)} Z`
  );
}

export const BOARD_SEGMENTS: readonly BoardSegment[] = Array.from(
  { length: SECTOR_COUNT },
  (_, index) => index,
).flatMap((index) => {
  const single = isRedSector(index) ? 'dark' : 'light';
  const ring = isRedSector(index) ? 'red' : 'green';
  return [
    { d: band(index, BULL_RADIUS, TRIPLE_INNER_RADIUS), tone: single },
    { d: band(index, TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS), tone: ring },
    { d: band(index, TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS), tone: single },
    { d: band(index, DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS), tone: ring },
  ] satisfies BoardSegment[];
});

export const BOARD_SECTOR_NUMBERS: readonly SectorNumber[] = SECTOR_ORDER.map(
  (value, index) => {
    const angle = sectorCentreAngle(index);
    const [x, y] = toSvg(NUMBER_RADIUS * Math.cos(angle), NUMBER_RADIUS * Math.sin(angle));
    return { x, y, value };
  },
);
