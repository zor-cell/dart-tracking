/** Client -> server: let this device speak the booked darts from now on. */
export interface ClaimAnnouncerDto {
  readonly type: 'claim_announcer';
}
