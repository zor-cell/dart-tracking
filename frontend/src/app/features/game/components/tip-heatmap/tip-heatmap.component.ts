import { DOCUMENT, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  model,
  signal,
} from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import {
  BOARD_BACKING_RADIUS,
  BOARD_VIEW_EXTENT,
  boardViewBox,
  fieldOutline,
  offBoardArrowPath,
  offBoardMark,
} from '../../models/board-face';
import { toSvg } from '../../models/board-geometry';
import { fieldName } from '../../models/field-label';
import { HEAT_CUTOFF, cssColor, heatColor } from '../../models/heat-colors';
import { TipDensity, TipPoint, tipDensity } from '../../models/tip-density';
import { BoardFaceComponent, FieldEnter } from '../board-face/board-face.component';
import { DartMarkersComponent } from '../dart-markers/dart-markers.component';
import { HeatLegendComponent } from '../heat-legend/heat-legend.component';

/** Radius of every tip, old and current alike, in board millimetres. */
const TIP_RADIUS = 4.5;

/** Edge of a density cell and how far each tip spreads, in board millimetres. */
const CLOUD_CELL = 2;
const CLOUD_SIGMA = 6;

/** A sparse cloud's spread for a single tip, and the least it narrows to, in board millimetres;
 * it shrinks with the sixth root of the tip count. */
const SPARSE_SIGMA = 20;
const SPARSE_MIN_SIGMA = 10;

/** Every tip as its own dot, or all of them smoothed into one cloud. */
export type TipHeatmapMode = 'dots' | 'cloud';

/** What the caption says about a picked field. */
export interface HeatmapPick {
  readonly name: string;
  readonly detail: string;
}

/** Every located tip on one board, with the visit under way marked on top as on the live board;
 * given `counts`, a tap or hover names a field's located darts. Projects `svg:g[overlay]`. */
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
  /** The visit under way, numbered and coloured on top. */
  readonly current = input<readonly DartDto[]>([]);
  readonly mode = input<TipHeatmapMode>('dots');
  /** Few tips, as in one game: the cloud has no cutoff and spreads wider the fewer there are. */
  readonly sparse = input(false);
  /** Located darts per field, keyed by called-out label; fields stay unpickable without them. */
  readonly counts = input<ReadonlyMap<string, number> | null>(null);
  /** A field the view picked itself, captioned in place of the summary. */
  readonly picked = input<HeatmapPick | null>(null);
  /** Half the drawn area, in board millimetres; the cloud covers all of it. */
  readonly extent = input(BOARD_VIEW_EXTENT);

  /** The field last tapped; bound by a view that keeps it across layers. */
  readonly pinned = model<string | null>(null);
  protected readonly hovered = signal<string | null>(null);

  protected readonly viewBox = computed(() => boardViewBox(this.extent()));
  protected readonly markRadius = TIP_RADIUS;
  protected readonly arrowPath = offBoardArrowPath(TIP_RADIUS);
  private readonly cutoff = computed(() => (this.sparse() ? 0 : HEAT_CUTOFF));
  protected readonly legendColor = (share: number): string =>
    cssColor(heatColor(share, this.cutoff()));

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

  /** Fields with darts, focusable so the keyboard reaches their counts. */
  protected readonly fields = computed(() =>
    [...(this.counts() ?? [])].flatMap(([label, count]) => {
      const d = fieldOutline(label, 0);
      const ariaLabel = `${fieldName(label)}: ${count} ${count === 1 ? 'Dart' : 'Darts'}`;
      return d === null ? [] : [{ label, d, ariaLabel }];
    }),
  );

  /** The field under the pointer or last tapped, hit or not. */
  protected readonly selected = computed(() => {
    const counts = this.counts();
    const label = this.hovered() ?? this.pinned();
    const outline = label === null ? null : fieldOutline(label, 0);
    if (counts === null || label === null || outline === null) {
      return null;
    }
    return { label, outline, name: fieldName(label), count: counts.get(label) ?? 0 };
  });

  /** The picked field as the caption names it, its share against every located dart. */
  protected readonly pick = computed<HeatmapPick | null>(() => {
    const field = this.selected();
    if (field === null) {
      return this.picked();
    }
    const located = [...(this.counts()?.values() ?? [])].reduce((sum, count) => sum + count, 0);
    const share = Math.round((field.count / Math.max(1, located)) * 100);
    const darts = `${field.count} ${field.count === 1 ? 'Dart' : 'Darts'}`;
    return {
      name: field.name,
      detail: field.count === 0 ? 'keine Treffer' : `${darts} · ${share} %`,
    };
  });

  protected readonly dots = computed(() => this.marks().filter((mark) => !mark.offBoard));

  private readonly sigma = computed(() =>
    this.sparse()
      ? Math.max(SPARSE_MIN_SIGMA, SPARSE_SIGMA * Math.pow(Math.max(1, this.total()), -1 / 6))
      : CLOUD_SIGMA,
  );

  protected readonly density = computed(() =>
    this.mode() === 'cloud' && this.points().length > 0
      ? tipDensity(this.points(), this.extent(), CLOUD_CELL, this.sigma())
      : null,
  );

  /** The cloud as an image to lay over the board. */
  protected readonly cloud = computed(() => {
    const density = this.density();
    return density === null ? null : this.paint(density);
  });

  /** A tap on a field picks it, a second tap or one beside the fields clears it. */
  protected onBoardClick(event: MouseEvent): void {
    if (this.counts() === null) {
      return;
    }
    const label = (event.target as Element).getAttribute('data-label');
    this.pinned.update((pinned) => (label === null || label === pinned ? null : label));
  }

  protected onFieldEnter({ event, label }: FieldEnter): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(label);
    }
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
    const cutoff = this.cutoff();
    shares.forEach((share, index) => {
      image.data.set(heatColor(share, cutoff), index * 4);
    });
    context.putImageData(image, 0, 0);
    return canvas.toDataURL();
  }
}
