import { DOCUMENT, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import {
  BOARD_BACKING_RADIUS,
  BOARD_VIEW_BOX,
  BOARD_VIEW_EXTENT,
  offBoardArrowPath,
  offBoardMark,
} from '../../models/board-face';
import { toSvg } from '../../models/board-geometry';
import { cssColor, heatColor } from '../../models/heat-colors';
import { TipDensity, TipPoint, tipDensity } from '../../models/tip-density';
import { BoardFaceComponent } from '../board-face/board-face.component';
import { DartMarkersComponent } from '../dart-markers/dart-markers.component';
import { HeatLegendComponent } from '../heat-legend/heat-legend.component';

/** Radius of every tip, old and current alike, in board millimetres. */
const TIP_RADIUS = 4.5;

/** Edge of a density cell and how far each tip spreads, in board millimetres. */
const CLOUD_CELL = 2;
const CLOUD_SIGMA = 6;

/** Every tip as its own dot, or all of them smoothed into one cloud. */
export type TipHeatmapMode = 'dots' | 'cloud';

/** Every located tip on one board, with the visit under way marked on top as on the live board.
 * Projects `svg:g[overlay]` over the board and `[caption]` in place of the count. */
@Component({
  selector: 'app-tip-heatmap',
  imports: [BoardFaceComponent, DartMarkersComponent, DecimalPipe, HeatLegendComponent],
  templateUrl: './tip-heatmap.component.html',
  styleUrl: './tip-heatmap.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TipHeatmapComponent {
  private readonly document = inject(DOCUMENT);

  readonly points = input.required<readonly TipPoint[]>();
  /** The visit under way, numbered and coloured on top; dots only. */
  readonly current = input<readonly DartDto[]>([]);
  readonly mode = input<TipHeatmapMode>('dots');

  protected readonly viewBox = BOARD_VIEW_BOX;
  /** Half the drawn area, in board millimetres; the cloud only counts tips beyond it. */
  protected readonly extent = BOARD_VIEW_EXTENT;
  protected readonly markRadius = TIP_RADIUS;
  protected readonly arrowPath = offBoardArrowPath(TIP_RADIUS);
  protected readonly legendColor = (share: number): string => cssColor(heatColor(share));

  private readonly total = computed(() =>
    this.points().reduce((sum, [, , count = 1]) => sum + count, 0),
  );

  protected readonly ariaLabel = computed(() => `Dartscheibe mit ${this.total()} erkannten Darts`);

  /** How many darts the camera placed, written in the corner. */
  protected readonly caption = computed(() => {
    const total = this.total();
    return total === 0
      ? 'Keine Darts erkannt'
      : `${total} ${total === 1 ? 'Dart' : 'Darts'} erkannt`;
  });

  protected readonly marks = computed(() =>
    this.mode() === 'dots'
      ? this.points().map(([x, y]) => {
          const [svgX, svgY] = toSvg(x, y);
          return { x: svgX, y: svgY, offBoard: Math.hypot(svgX, svgY) > BOARD_BACKING_RADIUS };
        })
      : [],
  );

  /** Tips off the board as arrows on the margin ring, aimed the way they lie, as on the live board. */
  protected readonly arrows = computed(() =>
    this.marks()
      .filter((mark) => mark.offBoard)
      .map((mark) => {
        const { x, y, angle } = offBoardMark(mark.x, mark.y);
        return `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${angle.toFixed(2)})`;
      }),
  );

  protected readonly dots = computed(() => this.marks().filter((mark) => !mark.offBoard));

  protected readonly density = computed(() =>
    this.mode() === 'cloud' && this.points().length > 0
      ? tipDensity(this.points(), BOARD_VIEW_EXTENT, CLOUD_CELL, CLOUD_SIGMA)
      : null,
  );

  /** The cloud as an image to lay over the board. */
  protected readonly cloud = computed(() => {
    const density = this.density();
    return density === null ? null : this.paint(density);
  });

  private paint({ size, shares }: TipDensity): string {
    const canvas = this.document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext('2d');
    if (context === null) {
      return '';
    }
    const image = context.createImageData(size, size);
    shares.forEach((share, index) => {
      image.data.set(heatColor(share), index * 4);
    });
    context.putImageData(image, 0, 0);
    return canvas.toDataURL();
  }
}
