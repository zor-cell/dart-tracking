/** Client -> server: what every game command carries besides its own fields. */
export interface GameCommandDto {
  readonly revision?: number; // revision of the state the command was made against
}
