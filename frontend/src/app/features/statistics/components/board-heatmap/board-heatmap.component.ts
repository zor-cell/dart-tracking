import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
  BOARD_VIEW_BOX,
  fieldLabelPoint,
  fieldOutline,
} from '../../../game/models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS, toSvg } from '../../../game/models/board-geometry';
import { HeatmapPoint } from '../../dto/player-statistics.dto';

/**
 * Every located tip on one board. Drawn as translucent dots that add up where
 * throws cluster, so density is the message rather than any single dart.
 *
 * Manually entered darts have no position, so they tint their field instead,
 * darker the more of them landed there.
 */
@Component({
  selector: 'app-board-heatmap',
  templateUrl: './board-heatmap.component.html',
  styleUrl: './board-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BoardHeatmapComponent {
  readonly points = input.required<readonly HeatmapPoint[]>();
  /** Called-out fields of manually entered darts, one entry per dart. */
  readonly fields = input<readonly string[]>([]);

  protected readonly segments = BOARD_SEGMENTS;
  protected readonly sectorNumbers = BOARD_SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly backingRadius = BOARD_BACKING_RADIUS;
  protected readonly viewBox = BOARD_VIEW_BOX;

  protected readonly fieldMarks = computed(() => {
    const counts = new Map<string, number>();
    for (const label of this.fields()) {
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    const most = Math.max(1, ...counts.values());
    return [...counts].flatMap(([label, count]) => {
      const d = fieldOutline(label, 0);
      const point = fieldLabelPoint(label);
      if (d === null || point === null) {
        return [];
      }
      return [{ d, x: point[0], y: point[1], count, opacity: 0.25 + (0.5 * count) / most }];
    });
  });

  protected readonly ariaLabel = computed(() => {
    const entered = this.fields().length;
    const located = `Dartscheibe mit ${this.points().length} erkannten Treffern`;
    return entered === 0 ? located : `${located} und ${entered} eingegebenen`;
  });

  protected readonly marks = computed(() =>
    this.points().map(([x, y]) => {
      const [svgX, svgY] = toSvg(x, y);
      return { x: svgX, y: svgY };
    }),
  );
}
