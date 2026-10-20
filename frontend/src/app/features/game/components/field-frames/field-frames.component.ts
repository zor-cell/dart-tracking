import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DartDto } from '../../dto/dart.dto';
import { fieldLabelPoint, fieldOutline } from '../../models/board-face';
import { dartColor } from '../../models/dart-colors';

/** Stroke width of a field frame, in board millimetres. */
const FRAME_WIDTH = 3.2;

/** How much further in each further frame on the same field sits, in board millimetres. */
const FRAME_STEP = 1.5;

/** A field darts of the visit landed in: one inset frame and one ordinal per dart. */
interface FramedField {
  readonly x: number;
  readonly y: number;
  readonly frames: { readonly d: string; readonly color: string }[];
  readonly ordinals: { readonly value: number; readonly color: string }[];
}

/** A visit's darts framed in the field they hit, numbered as thrown. Used on an SVG `<g>`. */
@Component({
  selector: '[app-field-frames]',
  templateUrl: './field-frames.component.html',
  styleUrl: './field-frames.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FieldFramesComponent {
  /** The visit's darts in throwing order. */
  readonly darts = input.required<readonly DartDto[]>();
  /** Frame located darts too; otherwise only entered ones, whose tip is unknown. */
  readonly includeLocated = input(false);

  protected readonly frameWidth = FRAME_WIDTH;

  protected readonly fields = computed<FramedField[]>(() => {
    const fields = new Map<string, FramedField>();
    this.darts().forEach((dart, index) => {
      if (dart.position !== null && !this.includeLocated()) {
        return;
      }
      const point = fieldLabelPoint(dart.label);
      if (point === null) {
        return;
      }
      const field = fields.get(dart.label) ?? {
        x: point[0],
        y: point[1],
        frames: [],
        ordinals: [],
      };
      const inset = FRAME_WIDTH / 2 + Math.min(field.frames.length, 2) * FRAME_STEP;
      const color = dartColor(index);
      field.frames.push({ d: fieldOutline(dart.label, inset) ?? '', color });
      field.ordinals.push({ value: index + 1, color });
      fields.set(dart.label, field);
    });
    return [...fields.values()];
  });
}
