/** Client -> server: take the win for the whole room, or go back to it from the finished screen. */
export interface SetWinConfirmedDto {
  readonly type: 'set_win_confirmed';
  readonly confirmed: boolean;
}
