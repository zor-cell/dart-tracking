/** Server -> room: which device currently speaks the booked darts, if any. */
export interface AnnouncerStateDto {
  readonly type: 'announcer_state';
  readonly clientId: string | null;
}
