/** An entry in the signed-in account's address book. */
export interface PlayerIdentityDto {
  readonly id: string;
  readonly name: string;
  readonly isSelf: boolean;
}
