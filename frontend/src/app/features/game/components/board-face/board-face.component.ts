import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import {
  BOARD_BACKING_RADIUS,
  BOARD_SECTOR_NUMBERS,
  BOARD_SEGMENTS,
} from '../../models/board-face';
import { BULLSEYE_RADIUS, BULL_RADIUS } from '../../models/board-geometry';

/** A field the pointer entered, by its called-out label. */
export interface FieldEnter {
  readonly event: PointerEvent;
  readonly label: string;
}

/** The empty board every board view draws on: beds, bull, number ring. Used on an SVG `<g>`;
 * projected content lies between the beds and the numbers. */
@Component({
  selector: '[app-board-face]',
  templateUrl: './board-face.component.html',
  styleUrl: './board-face.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.face--faded]': 'faded()', '[class.face--interactive]': 'interactive()' },
})
export class BoardFaceComponent {
  /** Grey and faded beds, for views whose own fills carry the information. */
  readonly faded = input(false);
  /** Report the field under the pointer; every bed carries its label as `data-label` anyway. */
  readonly interactive = input(false);

  readonly fieldEnter = output<FieldEnter>();
  readonly fieldLeave = output<void>();

  protected readonly segments = BOARD_SEGMENTS;
  protected readonly sectorNumbers = BOARD_SECTOR_NUMBERS;
  protected readonly bullRadius = BULL_RADIUS;
  protected readonly bullseyeRadius = BULLSEYE_RADIUS;
  protected readonly backingRadius = BOARD_BACKING_RADIUS;

  protected enter(event: PointerEvent, label: string): void {
    if (this.interactive()) {
      this.fieldEnter.emit({ event, label });
    }
  }

  protected leave(): void {
    if (this.interactive()) {
      this.fieldLeave.emit();
    }
  }
}
