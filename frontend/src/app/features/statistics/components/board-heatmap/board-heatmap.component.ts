import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
  BOARD_VIEW_BOX,
} from '../../../game/models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS, toSvg } from '../../../game/models/board-geometry';
import { HeatmapPoint } from '../../dto/player-statistics.dto';

/**
 * Every located tip on one board. Drawn as translucent dots that add up where
 * throws cluster, so density is the message rather than any single dart.
 *
 * Only camera-tracked darts carry a position, so a manually scored history
 * plots nothing — the page says so instead of showing an empty board.
 */
@Component({
  selector: 'app-board-heatmap',
  templateUrl: './board-heatmap.component.html',
  styleUrl: './board-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BoardHeatmapComponent {
  readonly points = input.required<readonly HeatmapPoint[]>();

  protected readonly segments = BOARD_SEGMENTS;
  protected readonly sectorNumbers = BOARD_SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly backingRadius = BOARD_BACKING_RADIUS;
  protected readonly viewBox = BOARD_VIEW_BOX;

  protected readonly marks = computed(() =>
    this.points().map(([x, y]) => {
      const [svgX, svgY] = toSvg(x, y);
      return { x: svgX, y: svgY };
    }),
  );
}
