/** Server -> announcer: a dart the camera just booked. `visitPoints` is set once
 * the visit is full, busted or won. */
export interface DartAnnouncementDto {
  readonly type: 'dart_announcement';
  readonly value: number;
  readonly multiplier: number;
  readonly visitPoints: number | null;
  readonly busted: boolean;
  readonly won: boolean;
}
