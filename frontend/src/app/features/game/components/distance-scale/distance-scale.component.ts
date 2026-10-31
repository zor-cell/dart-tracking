import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  BULL_RADIUS,
  BULLSEYE_RADIUS,
  DOUBLE_INNER_RADIUS,
  DOUBLE_OUTER_RADIUS,
  SECTOR_ANGLE,
  TRIPLE_INNER_RADIUS,
  TRIPLE_OUTER_RADIUS,
} from '../../models/board-geometry';
import { dartColor } from '../../models/dart-colors';

/** From the double's inner edge inward, or two darts of one visit around the treble. */
export type DistanceKind = 'checkout' | 'grouping';

const TRIPLE_CENTRE = (TRIPLE_INNER_RADIUS + TRIPLE_OUTER_RADIUS) / 2;

/** One ring band of a sector pointing up, the bullseye at the origin. */
function band(inner: number, outer: number): string {
  const point = (radius: number, side: number): string => {
    const angle = (side * SECTOR_ANGLE) / 2;
    return `${(radius * Math.sin(angle)).toFixed(2)} ${(-radius * Math.cos(angle)).toFixed(2)}`;
  };
  return (
    `M ${point(outer, -1)} A ${outer} ${outer} 0 0 1 ${point(outer, 1)} ` +
    `L ${point(inner, 1)} A ${inner} ${inner} 0 0 0 ${point(inner, -1)} Z`
  );
}

const BANDS = [
  { d: band(0, BULLSEYE_RADIUS), tone: 'red' },
  { d: band(BULLSEYE_RADIUS, BULL_RADIUS), tone: 'green' },
  { d: band(BULL_RADIUS, TRIPLE_INNER_RADIUS), tone: 'light' },
  { d: band(TRIPLE_INNER_RADIUS, TRIPLE_OUTER_RADIUS), tone: 'green' },
  { d: band(TRIPLE_OUTER_RADIUS, DOUBLE_INNER_RADIUS), tone: 'light' },
  { d: band(DOUBLE_INNER_RADIUS, DOUBLE_OUTER_RADIUS), tone: 'green' },
] as const;

/** One board sector to scale with a distance (mm) drawn across it, so a reader can place it. */
@Component({
  selector: 'app-distance-scale',
  templateUrl: './distance-scale.component.html',
  styleUrl: './distance-scale.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DistanceScaleComponent {
  readonly distance = input.required<number>();
  readonly kind = input.required<DistanceKind>();

  protected readonly bands = BANDS;
  protected readonly dartColor = dartColor;

  /** The gap along the centre line as SVG y of its ends, cut to the board, and the darts on it:
   * both ends for two darts of a visit, only the inner one for a dart short of the double. */
  protected readonly gap = computed(() => {
    const checkout = this.kind() === 'checkout';
    const room = checkout ? DOUBLE_INNER_RADIUS : DOUBLE_OUTER_RADIUS;
    const length = Math.min(Math.max(0, this.distance()), room);
    const outer = checkout ? room : Math.min(room, TRIPLE_CENTRE + length / 2);
    const inner = outer - length;
    return { from: -outer, to: -inner, darts: checkout ? [-inner] : [-outer, -inner] };
  });
}
