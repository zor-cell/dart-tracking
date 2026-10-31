import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { BoardFaceComponent } from '../../../game/components/board-face/board-face.component';
import { dartColor } from '../../../game/models/dart-colors';

/** Which figure the sketch explains. */
export type StatSketchKind = 'grouping' | 'checkout' | 'spread';

type Point = readonly [x: number, y: number];

/** A dashed distance, written in mm at `label`. */
interface Gap {
  readonly from: Point;
  readonly to: Point;
  readonly label: Point;
}

/** A zoom onto the board, in SVG board millimetres (y down), with darts and their distances. */
interface BoardScene {
  readonly viewBox: string;
  readonly darts: readonly Point[];
  readonly gaps: readonly Gap[];
  /** Where a hit's 0 mm is written; it counts into the average like a gap. */
  readonly hits: readonly Point[];
}

const [FIRST, SECOND, THIRD]: readonly Point[] = [
  [-8, -117],
  [9, -103],
  [-3, -91],
];

/** Sector 20 across the treble, three darts of one visit and the gaps between them. */
const GROUPING: BoardScene = {
  viewBox: '-48 -128 96 44',
  darts: [FIRST, SECOND, THIRD],
  gaps: [
    { from: FIRST, to: SECOND, label: [4, -112] },
    { from: FIRST, to: THIRD, label: [-21, -103] },
    { from: SECOND, to: THIRD, label: [6, -94] },
  ],
  hits: [],
};

/** Sector 20 around its double: one dart in it, one short and one beyond, each to the edge. */
const CHECKOUT: BoardScene = {
  viewBox: '-48 -184 96 44',
  darts: [
    [4, -165],
    [-12, -146],
    [16, -176],
  ],
  gaps: [
    { from: [-12, -146], to: [-13.1, -159.5], label: [-9, -150] },
    { from: [16, -176], to: [15.4, -169.3], label: [19, -175] },
  ],
  hits: [[7, -163.5]],
};

/** Centre of sector 20's treble, where the spread clouds sit. */
const TREBLE_20: Point = [0, -102.4];

/** `count` tips around the treble, spread `sx` by `sy` mm; the same tips on every draw. */
function cloud(sx: number, sy: number, count = 28): Point[] {
  let seed = 7;
  const random = (): number => (seed = (seed * 16807) % 2147483647) / 2147483647;
  return Array.from({ length: count }, (): Point => {
    const radius = Math.sqrt(-2 * Math.log(random()));
    const angle = 2 * Math.PI * random();
    return [
      TREBLE_20[0] + radius * Math.cos(angle) * sx,
      TREBLE_20[1] + radius * Math.sin(angle) * sy,
    ];
  });
}

/** One zoom of the spread comparison: a cloud and the ellipse that describes it, in mm. */
interface SpreadPanel {
  readonly tips: readonly Point[];
  readonly rx: number;
  readonly ry: number;
  readonly caption: string;
}

/** The same tips twice, once even and once stretched, so the ratio reads as a shape. */
const SPREAD: readonly SpreadPanel[] = [
  { tips: cloud(6, 6), rx: 12, ry: 12, caption: '1,0× rund' },
  { tips: cloud(4, 10), rx: 8, ry: 20, caption: '2,5× länglich' },
];

/** A gap's length in whole millimetres, as the sketch writes it. */
function millimetres({ from, to }: Gap): number {
  return Math.round(Math.hypot(to[0] - from[0], to[1] - from[1]));
}

/** The mean of the written distances, hits as 0 mm, the way the figure itself averages. */
function average({ gaps, hits }: BoardScene): number {
  const total = gaps.reduce((sum, gap) => sum + millimetres(gap), 0);
  return Math.round(total / (gaps.length + hits.length));
}

/** A small drawing that shows what a distance or shape figure measures, for its explanation. */
@Component({
  selector: 'app-stat-sketch',
  imports: [BoardFaceComponent],
  templateUrl: './stat-sketch.component.html',
  styleUrl: './stat-sketch.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatSketchComponent {
  readonly kind = input.required<StatSketchKind>();

  protected readonly dartColor = dartColor;
  protected readonly millimetres = millimetres;
  protected readonly average = average;
  protected readonly spread = SPREAD;
  protected readonly spreadViewBox = '-30 -126 60 47.5';
  protected readonly centre = TREBLE_20;

  /** The board zoom for a distance figure; null for the spread, which compares two zooms. */
  protected readonly scene = computed(() => {
    switch (this.kind()) {
      case 'grouping':
        return GROUPING;
      case 'checkout':
        return CHECKOUT;
      default:
        return null;
    }
  });
}
