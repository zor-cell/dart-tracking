import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { fieldOutline } from '../../../game/models/board-face';
import {
  DOUBLE_INNER_RADIUS,
  DOUBLE_OUTER_RADIUS,
  toSvg,
} from '../../../game/models/board-geometry';
import { fieldName } from '../../../game/models/field-label';
import { DoubleStatisticsDto, MissDirection } from '../../dto/double-statistics.dto';
import { MISS_DIRECTION_LABELS, missShares } from '../../models/miss-direction';

/** Middle of the double ring, in mm from the centre. */
const DOUBLE_MID_RADIUS = (DOUBLE_INNER_RADIUS + DOUBLE_OUTER_RADIUS) / 2;

/** Half the drawn area at the least and at the most, in mm. */
const MIN_HALF_WIDTH = 40;
const MIN_HALF_HEIGHT = 25;
const MAX_HALF = 90;

/** Fields drawn around a double turned to the top: D20 with its neighbours. */
const TURNED_TARGET = 'D20';
const TURNED_NEIGHBOURS = ['D5', 'D1', '5', '1', '20'];

/** Where the located darts at one double landed, the double turned to the top. */
@Component({
  selector: 'app-double-throws',
  imports: [DecimalPipe],
  templateUrl: './double-throws.component.html',
  styleUrl: './double-throws.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DoubleThrowsComponent {
  readonly double = input.required<DoubleStatisticsDto>();

  protected readonly name = computed(() => fieldName(this.double().label));
  protected readonly rate = computed(() => this.double().hits / this.double().attempts);
  private readonly bull = computed(() => this.double().label === '50');

  protected readonly target = computed(() => fieldOutline(this.bull() ? '50' : TURNED_TARGET, 0));
  protected readonly neighbours = computed(() =>
    (this.bull() ? ['25'] : TURNED_NEIGHBOURS).map((label) => fieldOutline(label, 0) ?? ''),
  );

  /** Misses first, so the hits are drawn on top of them. */
  protected readonly points = computed(() =>
    this.double()
      .throws.map(([across, out, hit]) => {
        const [x, y] = this.bull() ? toSvg(across, out) : toSvg(across, DOUBLE_MID_RADIUS + out);
        return { x, y, hit };
      })
      .sort((a, b) => Number(a.hit) - Number(b.hit)),
  );

  /** Fits every dart, centred on the double; far strays fall outside. */
  private readonly frame = computed(() => {
    const [cx, cy] = this.bull() ? [0, 0] : toSvg(0, DOUBLE_MID_RADIUS);
    const points = this.points();
    const half = (axis: 'x' | 'y', centre: number, least: number) =>
      Math.min(
        MAX_HALF,
        Math.max(least, ...points.map((point) => Math.abs(point[axis] - centre) + 4)),
      );
    return { cx, cy, hx: half('x', cx, MIN_HALF_WIDTH), hy: half('y', cy, MIN_HALF_HEIGHT) };
  });

  protected readonly viewBox = computed(() => {
    const { cx, cy, hx, hy } = this.frame();
    return `${cx - hx} ${cy - hy} ${2 * hx} ${2 * hy}`;
  });

  protected readonly dotRadius = computed(() => Math.max(this.frame().hx, this.frame().hy) / 60);

  /** The side most misses went to, with its share; null for the bull or without misses. */
  protected readonly tendency = computed(() => {
    const shares = missShares(this.double().directions);
    if (shares === null) {
      return null;
    }
    const [direction, share] = (Object.entries(shares) as [MissDirection, number][]).reduce(
      (best, entry) => (entry[1] > best[1] ? entry : best),
    );
    return { label: MISS_DIRECTION_LABELS[direction], share };
  });
}
