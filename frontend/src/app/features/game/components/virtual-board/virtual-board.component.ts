import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import { dartColor } from '../../models/dart-colors';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
  BOARD_VIEW_BOX,
  OFF_BOARD_MARKER_RADIUS,
  fieldLabelPoint,
  fieldOutline,
} from '../../models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS, toSvg } from '../../models/board-geometry';

/** How far the ordinal sits from the arrow, across the direction it points. */
const OFF_BOARD_LABEL_OFFSET = 18;

/** An arrowhead pointing along +x, aimed by the marker's own rotation. */
const ARROW_PATH = 'M 9.5 0 L -5 -7 L -5 7 Z';

/** Radius of the dot marking a located tip, in board millimetres. */
const MARKER_RADIUS = 5.5;

/** Stroke width of a manually entered dart's field frame, in board millimetres. */
const FRAME_WIDTH = 3.2;

/** How much further in each further frame on the same field sits, in board millimetres. */
const FRAME_STEP = 1.5;

/** A dart drawn where its tip was located, or aimed off the board. */
interface DartMarker {
  readonly x: number;
  readonly y: number;
  readonly labelX: number;
  readonly labelY: number;
  readonly label: string;
  /** Position within the visit (1–3), the tie to the dart boxes above. */
  readonly ordinal: number;
  /** The colour of this dart's outline on the camera phone (`dartColor`). */
  readonly color: string;
  /** Places and aims the arrow; null for a tip that is on the board. */
  readonly arrowTransform: string | null;
}

/** A field that manually entered darts landed in: one inset frame per dart. */
interface EnteredField {
  readonly x: number;
  readonly y: number;
  readonly frames: { readonly d: string; readonly color: string }[];
  readonly ordinals: { readonly value: number; readonly color: string }[];
}

/**
 * A drawn dartboard with the located tips plotted on it — what a device without
 * a camera has instead of the picture. The camera usually stands off to one
 * side, so its view answers "was something found" but not "where"; this answers
 * where, straight-on, for everyone in the room.
 *
 * Tracked darts are drawn at their tip; manually entered ones frame their field.
 */
@Component({
  selector: 'app-virtual-board',
  templateUrl: './virtual-board.component.html',
  styleUrl: './virtual-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VirtualBoardComponent {
  /** The current visit's darts, drawn large and numbered as thrown. */
  readonly darts = input.required<readonly DartDto[]>();

  protected readonly segments = BOARD_SEGMENTS;
  protected readonly sectorNumbers = BOARD_SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly backingRadius = BOARD_BACKING_RADIUS;
  protected readonly viewBox = BOARD_VIEW_BOX;

  protected readonly arrowPath = ARROW_PATH;
  protected readonly markerRadius = MARKER_RADIUS;
  protected readonly frameWidth = FRAME_WIDTH;

  protected readonly markers = computed<DartMarker[]>(() =>
    this.darts().flatMap((dart, index): DartMarker[] => {
      if (dart.position === null) {
        return [];
      }
      const [x, y] = toSvg(dart.position[0], dart.position[1]);
      const shared = { label: dart.label, ordinal: index + 1, color: dartColor(index) };
      const radius = Math.hypot(x, y);

      if (radius <= BOARD_BACKING_RADIUS) {
        return [{ ...shared, x, y, labelX: x + 11, labelY: y - 11, arrowTransform: null }];
      }

      // Off the board there is nothing to point at, so the marker keeps only the
      // direction: an arrow on the margin ring, aimed the way the dart flew.
      const unitX = x / radius;
      const unitY = y / radius;
      const markerX = unitX * OFF_BOARD_MARKER_RADIUS;
      const markerY = unitY * OFF_BOARD_MARKER_RADIUS;
      const angle = (Math.atan2(unitY, unitX) * 180) / Math.PI;
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

  protected readonly enteredFields = computed<EnteredField[]>(() => {
    const fields = new Map<string, EnteredField>();
    this.darts().forEach((dart, index) => {
      const point = dart.position === null ? fieldLabelPoint(dart.label) : null;
      if (point === null) {
        return;
      }
      const field = fields.get(dart.label) ?? { x: point[0], y: point[1], frames: [], ordinals: [] };
      const inset = FRAME_WIDTH / 2 + Math.min(field.frames.length, 2) * FRAME_STEP;
      const color = dartColor(index);
      field.frames.push({ d: fieldOutline(dart.label, inset) ?? '', color });
      field.ordinals.push({ value: index + 1, color });
      fields.set(dart.label, field);
    });
    return [...fields.values()];
  });

  protected readonly ariaLabel = computed(() => {
    const described = this.darts().flatMap((dart) => {
      if (dart.position === null) {
        return fieldLabelPoint(dart.label) === null ? [] : [`${dart.label}, eingegeben`];
      }
      const [x, y] = dart.position;
      return [Math.hypot(x, y) <= BOARD_BACKING_RADIUS ? dart.label : `${dart.label}, daneben`];
    });
    return described.length === 0
      ? 'Virtuelle Dartscheibe, keine Treffer dieser Runde'
      : `Virtuelle Dartscheibe mit ${described.length} Treffern dieser Runde: ${described.join(', ')}`;
  });
}
