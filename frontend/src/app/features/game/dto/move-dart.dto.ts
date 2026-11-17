import { DartCorrectionDto } from './dart-correction.dto';

/** Client -> server: move one dart of a visit to another place in it — for a
 * throw the camera missed, entered by hand and dragged back into order. */
export interface MoveDartDto extends DartCorrectionDto {
  readonly type: 'move_dart';
  readonly index: number;
  readonly toIndex: number;
}
