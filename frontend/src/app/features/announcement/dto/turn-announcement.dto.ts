/** Server -> announcer: the next visit is ready to be thrown by `player`.
 * `score` is the number the scoreboard shows for them. */
export interface TurnAnnouncementDto {
  readonly type: 'turn_announcement';
  readonly player: string;
  readonly score: number;
}
