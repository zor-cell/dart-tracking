import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CalibrationState } from '../../../calibration/dto/calibration-state.dto';
import { DartDto } from '../../dto/dart.dto';
import { BOARD_BACKING_RADIUS, BOARD_VIEW_BOX, fieldLabelPoint } from '../../models/board-face';
import { BoardFaceComponent } from '../board-face/board-face.component';
import { DartMarkersComponent } from '../dart-markers/dart-markers.component';
import { FieldFramesComponent } from '../field-frames/field-frames.component';

/** Stroke width of the calibration ring around the board, in board millimetres. */
const RING_WIDTH = 4;

/**
 * A drawn dartboard with the located tips plotted on it — what a device without
 * a camera has instead of the picture. Tracked darts are drawn at their tip;
 * manually entered ones frame their field.
 */
@Component({
  selector: 'app-virtual-board',
  imports: [BoardFaceComponent, DartMarkersComponent, FieldFramesComponent],
  templateUrl: './virtual-board.component.html',
  styleUrl: './virtual-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VirtualBoardComponent {
  /** The current visit's darts, drawn large and numbered as thrown. */
  readonly darts = input.required<readonly DartDto[]>();

  /** Darts located after a win or bust closed the visit, drawn faded after the booked ones. */
  readonly shadowDarts = input<readonly DartDto[]>([]);

  /** The room's calibration; a calibrated board gets a ring, a running attempt a pulsing one. */
  readonly calibration = input<CalibrationState | null>(null);

  protected readonly viewBox = BOARD_VIEW_BOX;
  protected readonly ringRadius = BOARD_BACKING_RADIUS + RING_WIDTH / 2;

  protected readonly ariaLabel = computed(() => {
    const shadows = this.shadowDarts().map((dart) => `${dart.label}, nicht gewertet`);
    const described = this.darts()
      .flatMap((dart) => {
        if (dart.position === null) {
          return fieldLabelPoint(dart.label) === null ? [] : [`${dart.label}, eingegeben`];
        }
        const [x, y] = dart.position;
        return [Math.hypot(x, y) <= BOARD_BACKING_RADIUS ? dart.label : `${dart.label}, daneben`];
      })
      .concat(shadows);
    return described.length === 0
      ? 'Virtuelle Dartscheibe, keine Treffer dieser Runde'
      : `Virtuelle Dartscheibe mit ${described.length} Treffern dieser Runde: ${described.join(', ')}`;
  });
}
