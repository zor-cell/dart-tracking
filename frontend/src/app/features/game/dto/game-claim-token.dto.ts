/** An anonymous game this device set up, with the token it was handed. */
export interface GameClaimTokenDto {
  readonly gameId: string;
  readonly token: string;
}
