/** Server -> previous game's room: the rematch to move over to. */
export interface RematchStartedDto {
  readonly type: 'rematch_started';
  readonly gameId: string;
}
