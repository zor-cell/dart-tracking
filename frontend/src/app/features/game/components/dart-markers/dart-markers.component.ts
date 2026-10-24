import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import {
  BOARD_BACKING_RADIUS,
  OFF_BOARD_MARKER_RADIUS,
  offBoardArrowPath,
  offBoardMark,
} from '../../models/board-face';
import { toSvg } from '../../models/board-geometry';
import { dartColor, SHADOW_DART_COLOR } from '../../models/dart-colors';

/** How far the ordinal sits from the arrow, across the direction it points. */
const OFF_BOARD_LABEL_OFFSET = 18;

/** Radius of the dot marking a located tip on the live board, in board millimetres. */
const MARKER_RADIUS = 5.5;

/** A dart drawn where its tip was located, or aimed off the board. */
interface DartMarker {
  readonly x: number;
  readonly y: number;
  readonly labelX: number;
  readonly labelY: number;
  /** Position within the visit (1–3), the tie to the dart boxes above. */
  readonly ordinal: number;
  /** The colour of this dart's outline on the camera phone (`dartColor`). */
  readonly color: string;
  /** Located after the visit closed; drawn faded, it scores nothing. */
  readonly shadow: boolean;
  /** Places and aims the arrow; null for a tip that is on the board. */
  readonly arrowTransform: string | null;
}

/** A visit's located tips, numbered and coloured as thrown. Used on an SVG `<g>`. */
@Component({
  selector: '[app-dart-markers]',
  templateUrl: './dart-markers.component.html',
  styleUrl: './dart-markers.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DartMarkersComponent {
  /** The visit's darts in throwing order; entered ones have no tip and are skipped. */
  readonly darts = input.required<readonly DartDto[]>();
  /** Darts located after a win or bust closed the visit, drawn faded after the booked ones. */
  readonly shadowDarts = input<readonly DartDto[]>([]);
  /** Dot radius in board millimetres. */
  readonly radius = input(MARKER_RADIUS);

  protected readonly arrowPath = computed(() => offBoardArrowPath(this.radius()));

  protected readonly markers = computed<DartMarker[]>(() =>
    [...this.darts(), ...this.shadowDarts()].flatMap((dart, index): DartMarker[] => {
      if (dart.position === null) {
        return [];
      }
      const [x, y] = toSvg(dart.position[0], dart.position[1]);
      const shadow = index >= this.darts().length;
      const color = shadow ? SHADOW_DART_COLOR : dartColor(index);
      const shared = { ordinal: index + 1, color, shadow };
      const radius = Math.hypot(x, y);

      if (radius <= BOARD_BACKING_RADIUS) {
        return [{ ...shared, x, y, labelX: x + 11, labelY: y - 11, arrowTransform: null }];
      }

      // Off the board there is nothing to point at, so the marker keeps only the
      // direction: an arrow on the margin ring, aimed the way the dart flew.
      const { x: markerX, y: markerY, angle } = offBoardMark(x, y);
      const unitX = markerX / OFF_BOARD_MARKER_RADIUS;
      const unitY = markerY / OFF_BOARD_MARKER_RADIUS;
      return [
        {
          ...shared,
          x: markerX,
          y: markerY,
          labelX: markerX - unitY * OFF_BOARD_LABEL_OFFSET,
          labelY: markerY + unitX * OFF_BOARD_LABEL_OFFSET,
          arrowTransform: `translate(${markerX.toFixed(2)} ${markerY.toFixed(2)}) rotate(${angle.toFixed(2)})`,
        },
      ];
    }),
  );
}
