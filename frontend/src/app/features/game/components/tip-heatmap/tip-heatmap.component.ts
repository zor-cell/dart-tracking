import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import {
  BOARD_BACKING_RADIUS,
  BOARD_VIEW_BOX,
  OFF_BOARD_MARKER_RADIUS,
} from '../../models/board-face';
import { toSvg } from '../../models/board-geometry';
import { BoardFaceComponent } from '../board-face/board-face.component';
import { DartMarkersComponent } from '../dart-markers/dart-markers.component';

/** Radius of every tip, old and current alike, in board millimetres. */
const TIP_RADIUS = 4;

/**
 * Every located tip on one board. Drawn as translucent dots that add up where
 * throws cluster, with the visit under way marked on top as on the live board.
 */
@Component({
  selector: 'app-tip-heatmap',
  imports: [BoardFaceComponent, DartMarkersComponent],
  templateUrl: './tip-heatmap.component.html',
  styleUrl: './tip-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TipHeatmapComponent {
  /** Located tips, `[x, y]` in board millimetres. */
  readonly points = input.required<readonly (readonly [number, number])[]>();
  /** The visit under way, numbered and coloured on top. */
  readonly current = input<readonly DartDto[]>([]);

  protected readonly viewBox = BOARD_VIEW_BOX;
  protected readonly markRadius = TIP_RADIUS;

  protected readonly ariaLabel = computed(
    () => `Dartscheibe mit ${this.points().length} erkannten Treffern`,
  );

  /** Tips off the board sit on the margin ring, the same place the live board aims its arrows. */
  protected readonly marks = computed(() =>
    this.points().map(([x, y]) => {
      const [svgX, svgY] = toSvg(x, y);
      const radius = Math.hypot(svgX, svgY);
      const scale = radius > BOARD_BACKING_RADIUS ? OFF_BOARD_MARKER_RADIUS / radius : 1;
      return { x: svgX * scale, y: svgY * scale };
    }),
  );
}
