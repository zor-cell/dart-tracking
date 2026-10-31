/**
 * The drawn dartboard: every ring band as an SVG path, plus the sector numbers.
 * Built once — the board is a fixed standard and never changes.
 */

import {
  BULLSEYE_RADIUS,
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
import { parseField } from './field-label';

/** One drawn ring band of one sector; `tone` picks the colour from the stylesheet. */
export interface BoardSegment {
  readonly d: string;
  readonly tone: 'dark' | 'light' | 'red' | 'green';
  /** The field the band belongs to, called out: 20, T20, D20. */
  readonly label: string;
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

/** An arrowhead pointing along +x, about as large as a dot of `radius`; aimed by the
 * marker's own rotation. */
export function offBoardArrowPath(radius: number): string {
  return `M ${1.2 * radius} 0 L ${-0.8 * radius} ${-0.9 * radius} L ${-0.8 * radius} ${0.9 * radius} Z`;
}

/** Where on the margin ring an off-board tip at SVG `[x, y]` is marked, and the
 * direction it lies in, in degrees. */
export function offBoardMark(x: number, y: number): { x: number; y: number; angle: number } {
  const radius = Math.hypot(x, y);
  return {
    x: (x / radius) * OFF_BOARD_MARKER_RADIUS,
    y: (y / radius) * OFF_BOARD_MARKER_RADIUS,
    angle: (Math.atan2(y, x) * 180) / Math.PI,
  };
}

/** Half the drawn area's edge length: the board, the off-board margin, and room
 * for the ordinal beside a marker out on it. */
export const BOARD_VIEW_EXTENT = 218;

/** The square view box `extent` mm around the bullseye. */
export function boardViewBox(extent: number): string {
  return `${-extent} ${-extent} ${extent * 2} ${extent * 2}`;
}

export const BOARD_VIEW_BOX = boardViewBox(BOARD_VIEW_EXTENT);

/**
 * One ring band of one sector as an SVG path, shrunk by `inset` mm on every side.
 * Angles grow counter-clockwise in board space, hence the differing sweep flags.
 */
function band(index: number, innerRadius: number, outerRadius: number, inset = 0): string {
  const centre = sectorCentreAngle(index);
  const half = SECTOR_ANGLE / 2;
  // The inset radial edges meet at `inset / sin(half)`; the band cannot start closer in.
  const inner = Math.max(innerRadius + inset, inset / Math.sin(half) + 0.01);
  const outer = outerRadius - inset;

  const point = (radius: number, side: -1 | 1): string => {
    const angle = centre + side * (half - Math.asin(inset / radius));
    const [x, y] = toSvg(radius * Math.cos(angle), radius * Math.sin(angle));
    return `${x.toFixed(2)} ${y.toFixed(2)}`;
  };

  return (
    `M ${point(inner, -1)}` +
    ` A ${inner} ${inner} 0 0 0 ${point(inner, 1)}` +
    ` L ${point(outer, 1)}` +
    ` A ${outer} ${outer} 0 0 1 ${point(outer, -1)} Z`
  );
}

/** A full circle as an SVG subpath. */
function circle(radius: number): string {
  return `M ${radius} 0 A ${radius} ${radius} 0 1 0 ${-radius} 0 A ${radius} ${radius} 0 1 0 ${radius} 0 Z`;
}

export const BOARD_SEGMENTS: readonly BoardSegment[] = Array.from(
  { length: SECTOR_COUNT },
  (_, index) => index,
).flatMap((index) => {
  const single = isRedSector(index) ? 'dark' : 'light';
  const ring = isRedSector(index) ? 'red' : 'green';
  const value = SECTOR_ORDER[index];
  return [
    { d: band(index, BULL_RADIUS, TRIPLE_INNER_RADIUS), tone: single, label: `${value}` },
    { d: band(index, TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS), tone: ring, label: `T${value}` },
    { d: band(index, TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS), tone: single, label: `${value}` },
    { d: band(index, DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS), tone: ring, label: `D${value}` },
  ] satisfies BoardSegment[];
});

export const BOARD_SECTOR_NUMBERS: readonly SectorNumber[] = SECTOR_ORDER.map(
  (value, index) => {
    const angle = sectorCentreAngle(index);
    const [x, y] = toSvg(NUMBER_RADIUS * Math.cos(angle), NUMBER_RADIUS * Math.sin(angle));
    return { x, y, value };
  },
);

/** Outline of the field `label` names, `inset` mm inside its edges; null for a miss. */
export function fieldOutline(label: string, inset: number): string | null {
  const field = parseField(label);
  if (field === null) {
    return null;
  }
  switch (field.ring) {
    case 'bullseye':
      return circle(BULLSEYE_RADIUS - inset);
    case 'bull':
      return `${circle(BULL_RADIUS - inset)} ${circle(BULLSEYE_RADIUS + inset)}`;
    case 'triple':
      return band(field.index, TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS, inset);
    case 'double':
      return band(field.index, DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS, inset);
    case 'single':
      return (
        `${band(field.index, BULL_RADIUS, TRIPLE_INNER_RADIUS, inset)} ` +
        band(field.index, TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS, inset)
      );
  }
}

/** Board radius (mm) the ordinals beside a single, triple or double field are written at. */
const FIELD_LABEL_RADIUS = { single: 57, triple: TRIPLE_INNER_RADIUS - 16, double: DOUBLE_INNER_RADIUS - 16 };

/** Distance (mm) of the bull's and the bullseye's ordinals from the centre. */
const BULL_LABEL_OFFSET = 28;

/** Where the ordinals of darts entered into the field `label` are written, in SVG units. */
export function fieldLabelPoint(label: string): readonly [number, number] | null {
  const field = parseField(label);
  if (field === null) {
    return null;
  }
  switch (field.ring) {
    case 'bullseye':
      return toSvg(0, BULL_LABEL_OFFSET);
    case 'bull':
      return toSvg(0, -BULL_LABEL_OFFSET);
    default: {
      const angle = sectorCentreAngle(field.index);
      const radius = FIELD_LABEL_RADIUS[field.ring];
      return toSvg(radius * Math.cos(angle), radius * Math.sin(angle));
    }
  }
}
