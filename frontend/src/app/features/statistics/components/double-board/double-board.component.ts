import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import { BoardFaceComponent } from '../../../game/components/board-face/board-face.component';
import {
  HeatBoardComponent,
  HeatField,
} from '../../../game/components/heat-board/heat-board.component';
import { TipHeatmapComponent } from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { BOARD_VIEW_BOX, fieldOutline } from '../../../game/models/board-face';
import {
  DOUBLE_INNER_RADIUS,
  DOUBLE_OUTER_RADIUS,
  SECTOR_ORDER,
  sectorCentreAngle,
} from '../../../game/models/board-geometry';
import { fieldName } from '../../../game/models/field-label';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { TipPoint } from '../../../game/models/tip-density';
import { DoubleStatisticsDto, MissDirection } from '../../dto/double-statistics.dto';
import { MISS_DIRECTION_LABELS, missShares } from '../../models/miss-direction';

/** Middle of the double ring, in mm from the centre. */
const DOUBLE_MID_RADIUS = (DOUBLE_INNER_RADIUS + DOUBLE_OUTER_RADIUS) / 2;

const BULL_ZOOM = '-60 -48 120 96';

/** How far the short and long chips and the side ones sit from the double's middle, in mm. */
const CHIP_RADIAL = 44;
const CHIP_SIDEWAYS = 55;

/** Half a chip's size and the room kept around the chips in a zoom, in SVG units. */
const CHIP_HALF_WIDTH = 17;
const CHIP_HALF_HEIGHT = 8;
const ZOOM_MARGIN = 8;

/** Width to height of a zoom, as the board's box. */
const ZOOM_ASPECT = 1.25;

/** A side's share around a zoomed double, with an arrow the way the darts missed. */
interface Chip {
  direction: MissDirection;
  /** Degrees the arrow points, clockwise from the right. */
  arrow: number;
  x: number;
  y: number;
}

const DIRECTIONS: readonly MissDirection[] = ['long', 'short', 'left', 'right'];

/** The darts thrown at a finishing double, as a tip cloud or as each double's hit rate.
 * A picked double narrows both; the cloud then zooms onto it. */
@Component({
  selector: 'app-double-board',
  imports: [
    BoardFaceComponent,
    DecimalPipe,
    FormsModule,
    HeatBoardComponent,
    NgTemplateOutlet,
    SelectButton,
    TipHeatmapComponent,
  ],
  templateUrl: './double-board.component.html',
  styleUrl: './double-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DoubleBoardComponent {
  readonly doubles = input.required<readonly DoubleStatisticsDto[]>();
  /** Label of the picked double. */
  readonly selected = model<string | null>(null);

  protected readonly hovered = signal<string | null>(null);
  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly layer = signal(storedHeatmapLayer());
  protected readonly miniViewBox = BOARD_VIEW_BOX;
  protected readonly labels = MISS_DIRECTION_LABELS;
  protected readonly directionOrder = DIRECTIONS;

  protected readonly selectable = (label: string): boolean =>
    this.doubles().some((double) => double.label === label);

  private readonly best = computed(() =>
    Math.max(0, ...this.doubles().map((double) => double.hits / double.attempts)),
  );

  protected readonly attempts = computed(() =>
    this.doubles().reduce((sum, double) => sum + double.attempts, 0),
  );

  protected readonly fields = computed<HeatField[]>(() =>
    this.doubles().map((double) => ({
      label: double.label,
      share: this.best() === 0 ? 0 : double.hits / double.attempts / this.best(),
      ariaLabel: `${fieldName(double.label)}: ${double.hits} von ${double.attempts} getroffen`,
    })),
  );

  protected readonly legendMax = computed(() => `${Math.round(this.best() * 100)} %`);

  private readonly picked = computed(
    () => this.doubles().find((double) => double.label === this.selected()) ?? null,
  );

  /** Where the darts at the picked double landed, or at every double without a pick. */
  protected readonly tips = computed<TipPoint[]>(() => {
    const picked = this.picked();
    return (picked ? [picked] : this.doubles()).flatMap((double) =>
      double.throws.map(([x, y]) => [x, y] as const),
    );
  });

  /** The cloud zooms onto a picked double. */
  protected readonly zoomed = computed(() => this.layer() === 'tips' && this.picked() !== null);

  /** Where each side's share sits around the picked double, as it hangs on the board. */
  private readonly places = computed(() => {
    const picked = this.picked();
    return picked === null || picked.label === '50' ? null : chipPlaces(picked.label);
  });

  protected readonly zoom = computed(() => {
    if (!this.zoomed()) {
      return null;
    }
    const places = this.places();
    return places === null ? BULL_ZOOM : zoomAround(places);
  });

  /** Each side's share of the misses: the picked double's, or all doubles' together. */
  private readonly shares = computed(() => {
    const picked = this.picked();
    const counts = { short: 0, long: 0, left: 0, right: 0 };
    for (const double of picked ? [picked] : this.doubles()) {
      for (const direction of DIRECTIONS) {
        counts[direction] += double.directions[direction];
      }
    }
    return missShares(counts);
  });

  /** The shares as chips around the zoomed double. */
  protected readonly chips = computed(() => {
    const shares = this.shares();
    const places = this.places();
    return this.zoomed() && shares !== null && places !== null
      ? places.map((place) => ({ ...place, share: shares[place.direction] }))
      : [];
  });

  /** The shares as one line under the board, whenever it is not zoomed. */
  protected readonly line = computed(() => (this.zoomed() ? null : this.shares()));

  /** Every double as a tap target over the tip cloud, with the hovered or picked one outlined. */
  protected readonly targets = computed(() =>
    this.doubles().map((double) => ({
      label: double.label,
      d: fieldOutline(double.label, 0) ?? '',
      ariaLabel: `${fieldName(double.label)}: ${double.hits} von ${double.attempts} getroffen`,
    })),
  );

  protected readonly outline = computed(() => {
    const label = this.hovered() ?? this.selected();
    return label === null ? null : fieldOutline(label, 0);
  });

  protected readonly pickedOutline = computed(() => {
    const picked = this.picked();
    return picked === null ? null : fieldOutline(picked.label, 0);
  });

  /** The double under the pointer or picked, with its rate. */
  protected readonly shown = computed(() => {
    const label = this.hovered() ?? this.selected();
    const double = this.doubles().find((entry) => entry.label === label);
    return double
      ? { ...double, name: fieldName(double.label), rate: double.hits / double.attempts }
      : null;
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }

  protected toggle(label: string, event: Event): void {
    event.stopPropagation();
    event.preventDefault();
    this.selected.update((picked) => (picked === label ? null : label));
  }

  protected onTargetEnter(label: string, event: PointerEvent): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(label);
    }
  }
}

/** The four chips around a double: short and long along its radius, the sides across it. */
function chipPlaces(label: string): Chip[] {
  const index = SECTOR_ORDER.indexOf(Number(label.slice(1)));
  const angle = sectorCentreAngle(index);
  const [outX, outY] = [Math.cos(angle), -Math.sin(angle)];
  const [leftX, leftY] = [-Math.sin(angle), -Math.cos(angle)];
  const [midX, midY] = [outX * DOUBLE_MID_RADIUS, outY * DOUBLE_MID_RADIUS];
  const place = (direction: MissDirection, dx: number, dy: number): Chip => ({
    direction,
    arrow: (Math.atan2(dy, dx) * 180) / Math.PI,
    x: midX + dx,
    y: midY + dy,
  });
  return [
    place('long', outX * CHIP_RADIAL, outY * CHIP_RADIAL),
    place('short', -outX * CHIP_RADIAL, -outY * CHIP_RADIAL),
    place('left', leftX * CHIP_SIDEWAYS, leftY * CHIP_SIDEWAYS),
    place('right', -leftX * CHIP_SIDEWAYS, -leftY * CHIP_SIDEWAYS),
  ];
}

/** The smallest box of the board's shape that holds every chip. */
function zoomAround(chips: readonly Chip[]): string {
  const left = Math.min(...chips.map((chip) => chip.x)) - CHIP_HALF_WIDTH - ZOOM_MARGIN;
  const right = Math.max(...chips.map((chip) => chip.x)) + CHIP_HALF_WIDTH + ZOOM_MARGIN;
  const top = Math.min(...chips.map((chip) => chip.y)) - CHIP_HALF_HEIGHT - ZOOM_MARGIN;
  const bottom = Math.max(...chips.map((chip) => chip.y)) + CHIP_HALF_HEIGHT + ZOOM_MARGIN;
  const width = Math.max(right - left, (bottom - top) * ZOOM_ASPECT);
  const height = width / ZOOM_ASPECT;
  const x = (left + right - width) / 2;
  const y = (top + bottom - height) / 2;
  return [x, y, width, height].map((value) => value.toFixed(2)).join(' ');
}
