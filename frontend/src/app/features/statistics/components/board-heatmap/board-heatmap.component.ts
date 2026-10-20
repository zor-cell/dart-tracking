import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
  BOARD_VIEW_BOX,
} from '../../../game/models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS, toSvg } from '../../../game/models/board-geometry';
import { HeatmapPoint } from '../../dto/player-statistics.dto';

export interface HighlightedTip {
  readonly point: HeatmapPoint;
  readonly color: string;
  /** Position within the visit (1–3), written beside the tip. */
  readonly ordinal: number;
}

/**
 * Every located tip on one board. Drawn as translucent dots that add up where
 * throws cluster, so density is the message rather than any single dart.
 */
@Component({
  selector: 'app-board-heatmap',
  templateUrl: './board-heatmap.component.html',
  styleUrl: './board-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BoardHeatmapComponent {
  readonly points = input.required<readonly HeatmapPoint[]>();
  /** Tips to draw solid on top in their own colour, such as the visit under way. */
  readonly highlighted = input<readonly HighlightedTip[]>([]);

  protected readonly segments = BOARD_SEGMENTS;
  protected readonly sectorNumbers = BOARD_SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly backingRadius = BOARD_BACKING_RADIUS;
  protected readonly viewBox = BOARD_VIEW_BOX;

  protected readonly ariaLabel = computed(
    () => `Dartscheibe mit ${this.points().length} erkannten Treffern`,
  );

  protected readonly marks = computed(() => this.points().map(svgPoint));
  protected readonly highlightMarks = computed(() =>
    this.highlighted().map((tip) => ({
      ...svgPoint(tip.point),
      color: tip.color,
      ordinal: tip.ordinal,
    })),
  );
}

function svgPoint([x, y]: HeatmapPoint): { x: number; y: number } {
  const [svgX, svgY] = toSvg(x, y);
  return { x: svgX, y: svgY };
}
