/** Client -> server: move one dart of the open visit to another place in it —
 * for a throw the camera missed, entered by hand and dragged back into order. */
export interface MoveDartDto {
  readonly type: 'move_dart';
  readonly index: number;
  readonly toIndex: number;
}
