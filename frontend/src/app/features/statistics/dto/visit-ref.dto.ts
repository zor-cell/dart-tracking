/** A visit to open in its game's replay; `visit` counts the game's visits with darts. */
export interface VisitRefDto {
  readonly gameId: string;
  readonly visit: number;
}
