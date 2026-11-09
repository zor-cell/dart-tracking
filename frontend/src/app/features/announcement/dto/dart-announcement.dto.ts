/** Server -> announcer: a dart just booked, tracked or entered by hand, and the clips calling it.
 * `visitPoints` is set once the visit is full, busted or won; `eliminated` names
 * whoever the dart sent back to zero. */
export interface DartAnnouncementDto {
  readonly type: 'dart_announcement';
  readonly value: number;
  readonly multiplier: number;
  readonly visitPoints: number | null;
  readonly busted: boolean;
  readonly won: boolean;
  readonly eliminated: readonly string[];
  readonly clips: readonly string[];
}
