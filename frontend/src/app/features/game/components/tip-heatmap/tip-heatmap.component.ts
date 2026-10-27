import { DOCUMENT, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
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

/** Half the area the cloud covers while zoomed, in board millimetres. */
const ZOOMED_CLOUD_EXTENT = 260;

/** How long a change of zoom takes to glide over, in milliseconds. */
const ZOOM_DURATION = 450;

type ViewBox = readonly [number, number, number, number];

/** Every tip as its own dot, or all of them smoothed into one cloud. */
export type TipHeatmapMode = 'dots' | 'cloud';

/** Every located tip on one board, with the visit under way marked on top as on the live board.
 * Projects `svg:g[overlay]` over the board and `[caption]` into the corner. */
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
  /** The part of the board to show, as an SVG viewBox; the whole board without one. */
  readonly zoom = input<string | null>(null);

  private readonly shownBox = signal<ViewBox>(parseViewBox(BOARD_VIEW_BOX));
  protected readonly view = computed(() => this.shownBox().join(' '));
  /** Half the area the cloud covers, in board millimetres: the drawn board, or more when a
   * zoom reaches past it. */
  protected readonly extent = computed(() =>
    this.zoom() === null ? BOARD_VIEW_EXTENT : ZOOMED_CLOUD_EXTENT,
  );
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
      ? tipDensity(this.points(), this.extent(), CLOUD_CELL, CLOUD_SIGMA)
      : null,
  );

  /** The cloud as an image to lay over the board. */
  protected readonly cloud = computed(() => {
    const density = this.density();
    return density === null ? null : this.paint(density);
  });

  constructor() {
    effect((onCleanup) => {
      const target = parseViewBox(this.zoom() ?? BOARD_VIEW_BOX);
      const from = untracked(this.shownBox);
      const view = this.document.defaultView;
      if (view === null || view.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        this.shownBox.set(target);
        return;
      }
      let start: number | null = null;
      let frame = 0;
      const step = (now: number): void => {
        start ??= now;
        const progress = Math.min((now - start) / ZOOM_DURATION, 1);
        this.shownBox.set(glide(from, target, ease(progress)));
        if (progress < 1) {
          frame = view.requestAnimationFrame(step);
        }
      };
      frame = view.requestAnimationFrame(step);
      onCleanup(() => view.cancelAnimationFrame(frame));
    });
  }

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

function parseViewBox(box: string): ViewBox {
  const [x, y, width, height] = box.split(' ').map(Number);
  return [x, y, width, height];
}

function ease(progress: number): number {
  return progress < 0.5 ? 2 * progress * progress : 1 - (-2 * progress + 2) ** 2 / 2;
}

/** The box part of the way from one to another: the centre moves evenly, the size by ratio,
 * so the zoom feels steady. */
function glide(from: ViewBox, to: ViewBox, progress: number): ViewBox {
  const width = from[2] * (to[2] / from[2]) ** progress;
  const height = from[3] * (to[3] / from[3]) ** progress;
  const centreX = from[0] + from[2] / 2 + (to[0] + to[2] / 2 - from[0] - from[2] / 2) * progress;
  const centreY = from[1] + from[3] / 2 + (to[1] + to[3] / 2 - from[1] - from[3] / 2) * progress;
  return [centreX - width / 2, centreY - height / 2, width, height];
}
