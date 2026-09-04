import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import { dartColor } from '../../models/dart-colors';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
  BOARD_VIEW_BOX,
} from '../../models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS, toSvg } from '../../models/board-geometry';

/** A dart drawn where its tip was located. */
interface DartMarker {
  readonly x: number;
  readonly y: number;
  readonly label: string;
  /** Position within the visit (1–3), the tie to the dart boxes above. */
  readonly ordinal: number;
  /** The colour of this dart's outline on the camera phone (`dartColor`). */
  readonly color: string;
}

/**
 * A drawn dartboard with the located tips plotted on it — what a device without
 * a camera has instead of the picture. The camera usually stands off to one
 * side, so its view answers "was something found" but not "where"; this answers
 * where, straight-on, for everyone in the room.
 *
 * Only tracked darts carry a position; manually entered ones are counted but
 * cannot be placed, which the caption spells out rather than silently omitting.
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

  protected readonly markers = computed<DartMarker[]>(() =>
    this.darts().flatMap((dart, index) => {
      if (dart.position === null) {
        return [];
      }
      const [x, y] = toSvg(dart.position[0], dart.position[1]);
      return [{ x, y, label: dart.label, ordinal: index + 1, color: dartColor(index) }];
    }),
  );

  protected readonly ariaLabel = computed(() => {
    const placed = this.markers();
    return placed.length === 0
      ? 'Virtuelle Dartscheibe, keine erkannten Treffer dieser Runde'
      : `Virtuelle Dartscheibe mit ${placed.length} erkannten Treffern dieser Runde: ` +
          placed.map((marker) => marker.label).join(', ');
  });
}
