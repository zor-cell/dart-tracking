export interface GameClaimDto {
  readonly token: string;
  /** The seat the account played on; null when it only kept score. */
  readonly seat: number | null;
}
