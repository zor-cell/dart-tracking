/** Server -> announcer: the next visit is ready to be thrown by `player`.
 * `remaining` is set in x01 when the visit can finish. */
export interface TurnAnnouncementDto {
  readonly type: 'turn_announcement';
  readonly player: string;
  readonly remaining: number | null;
}
