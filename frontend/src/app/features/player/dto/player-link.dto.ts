/** An entry in someone else's address book that is linked to this account. */
export interface PlayerLinkDto {
  readonly playerId: string;
  readonly playerName: string;
  readonly ownerName: string;
  /** Taken out of that address book; only the past games remain linked. */
  readonly retired: boolean;
}
