/** Client -> server: end the visit and hand over to the next player. */
export interface NextPlayerDto {
  readonly type: 'next_player';
}
