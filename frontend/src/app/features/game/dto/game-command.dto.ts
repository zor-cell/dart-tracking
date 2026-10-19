/** Client -> server: what every game command carries besides its own fields —
 * the open visit as the device saw it, so the server can refuse an outdated one. */
export interface GameCommandDto {
  readonly turnIndex?: number;
  readonly dartIndex?: number;
}
