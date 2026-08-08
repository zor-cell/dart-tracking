import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
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
} from '../../models/board-geometry';

/** One drawn ring band of one sector; `tone` picks the colour from the stylesheet. */
interface BoardSegment {
  readonly d: string;
  readonly tone: 'dark' | 'light' | 'red' | 'green';
}

/** A sector value drawn outside the double ring. */
interface SectorNumber {
  readonly x: number;
  readonly y: number;
  readonly value: number;
}

/** A dart drawn where its tip was located. */
interface DartMarker {
  readonly x: number;
  readonly y: number;
  readonly label: string;
  /** Position within the visit (1–3), the tie to the dart boxes above. */
  readonly ordinal: number;
}

/** Where the sector values sit, far enough out to clear the double ring. */
const NUMBER_RADIUS = 186;

/** Half of the drawn area's edge length, leaving room for the numbers. */
const VIEW_EXTENT = 200;

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

/** The whole board, built once: it is a fixed standard and never changes. */
const SEGMENTS: readonly BoardSegment[] = Array.from(
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

const SECTOR_NUMBERS: readonly SectorNumber[] = SECTOR_ORDER.map((value, index) => {
  const angle = sectorCentreAngle(index);
  const [x, y] = toSvg(NUMBER_RADIUS * Math.cos(angle), NUMBER_RADIUS * Math.sin(angle));
  return { x, y, value };
});

/**
 * A drawn dartboard with the located tips plotted on it — what a device without
 * a camera has instead of the picture. The camera usually stands off to one
 * side, so its view answers "was something found" but not "where"; this answers
 * where, straight-on, for everyone in the room.
 *
 * Only tracked darts carry a position; manually entered ones are counted but
 * cannot be placed, which the caption spells out rather than silently omitting.
 */
@Component({
  selector: 'app-virtual-board',
  templateUrl: './virtual-board.component.html',
  styleUrl: './virtual-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VirtualBoardComponent {
  /** The current visit's darts, drawn large and numbered as thrown. */
  readonly darts = input.required<readonly DartDto[]>();

  protected readonly segments = SEGMENTS;
  protected readonly sectorNumbers = SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly viewBox = `${-VIEW_EXTENT} ${-VIEW_EXTENT} ${VIEW_EXTENT * 2} ${VIEW_EXTENT * 2}`;

  protected readonly markers = computed<DartMarker[]>(() =>
    this.darts().flatMap((dart, index) => {
      if (dart.position === null) {
        return [];
      }
      const [x, y] = toSvg(dart.position[0], dart.position[1]);
      return [{ x, y, label: dart.label, ordinal: index + 1 }];
    }),
  );

  /** Darts of this visit that were entered by hand and so cannot be placed. */
  protected readonly unplacedCount = computed(
    () => this.darts().filter((dart) => dart.position === null).length,
  );

  protected readonly ariaLabel = computed(() => {
    const placed = this.markers();
    return placed.length === 0
      ? 'Virtuelle Dartscheibe, keine erkannten Treffer dieser Runde'
      : `Virtuelle Dartscheibe mit ${placed.length} erkannten Treffern dieser Runde: ` +
          placed.map((marker) => marker.label).join(', ');
  });
}
