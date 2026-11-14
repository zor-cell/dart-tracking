/** Client -> server: end a game nobody wins for the whole room, or go back into it. */
export interface SetEndedDto {
  readonly type: 'set_ended';
  readonly ended: boolean;
}
