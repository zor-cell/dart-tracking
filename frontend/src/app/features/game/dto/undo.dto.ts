/** Client -> server: step back one action — a dart, or the switch to the
 * current player. */
export interface UndoDto {
  readonly type: 'undo';
}
