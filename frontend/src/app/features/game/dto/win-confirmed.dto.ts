/** Server -> room: the winning visit's darts were pulled, so every device takes the win. */
export interface WinConfirmedDto {
  readonly type: 'win_confirmed';
}
