/** Server -> announcer: the next visit is ready to be thrown by `player`.
 * `score` is the number the scoreboard shows for them, null outside the points variants. */
export interface TurnAnnouncementDto {
  readonly type: 'turn_announcement';
  readonly player: string;
  readonly score: number | null;
  readonly clips: readonly string[];
}
